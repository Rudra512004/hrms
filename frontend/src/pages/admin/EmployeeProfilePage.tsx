import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { employeeDocumentService, type EmployeeDocument } from '../../services/employeeDocuments';
import { Card } from '../../components/Card';
import { StatusBadge } from '../../components/StatusBadge';
import {
  Loader2, ArrowLeft, Mail, Phone, MapPin, Building, Briefcase, Calendar,
  User as UserIcon, FileText, Upload, Download, Eye, Trash2, X, AlertCircle
} from 'lucide-react';
import { EmptyState } from '../../components/EmptyState';

const DOCUMENT_TYPES = [
  { value: 'identity', label: 'Identity Proof' },
  { value: 'address', label: 'Address Proof' },
  { value: 'education', label: 'Education' },
  { value: 'employment', label: 'Employment Record' },
  { value: 'contract', label: 'Contract / Offer' },
  { value: 'other', label: 'Other Document' },
];

const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx'];
const BLOCKED_EXTENSIONS = [
  '.exe', '.sh', '.bat', '.cmd', '.py', '.js', '.html', '.htm', '.php',
  '.vbs', '.ps1', '.rb', '.pl', '.jar', '.msi', '.dll', '.so', '.out',
  '.bin', '.run', '.com', '.pif', '.scr', '.reg', '.hta', '.cpl', '.inf',
];
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

export const EmployeeProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();

  const canViewDocs = hasPermission('employee.document.view');
  const canUploadDocs = hasPermission('employee.document.upload');
  const canDeleteDocs = hasPermission('employee.document.delete');

  const [employee, setEmployee] = useState<EmployeeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'contact' | 'employment' | 'documents'>('overview');

  // Documents state
  const [documents, setDocuments] = useState<EmployeeDocument[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docsError, setDocsError] = useState<string | null>(null);

  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDocType, setUploadDocType] = useState('identity');
  const [uploadDocName, setUploadDocName] = useState('');
  const [uploadDescription, setUploadDescription] = useState('');
  const [uploadExpiryDate, setUploadExpiryDate] = useState('');
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [uploadValidationError, setUploadValidationError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<number | null>(null);

  useEffect(() => {
    if (!id) return;
    const fetchProfile = async () => {
      setLoading(true);
      try {
        const data = await employeeManagementService.getEmployee(parseInt(id, 10));
        setEmployee(data);
        setError(null);
      } catch (err: any) {
        if (err.response?.status === 403) {
          setError("403 Forbidden: You do not have permission to view this profile.");
        } else if (err.response?.status === 404) {
          setError("404 Not Found: Employee does not exist.");
        } else {
          setError("Failed to load employee profile.");
        }
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [id]);

  const fetchDocuments = useCallback(async () => {
    if (!id || !canViewDocs) return;
    setDocsLoading(true);
    setDocsError(null);
    try {
      const docs = await employeeDocumentService.listDocuments(parseInt(id, 10));
      setDocuments(docs);
    } catch (err: any) {
      if (err.status === 403) {
        setDocsError("403 Forbidden: You do not have permission to view documents.");
      } else {
        setDocsError("Failed to load employee documents.");
      }
    } finally {
      setDocsLoading(false);
    }
  }, [id, canViewDocs]);

  useEffect(() => {
    if (activeTab === 'documents') {
      fetchDocuments();
    }
  }, [activeTab, fetchDocuments]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUploadValidationError(null);
    const file = e.target.files?.[0];
    if (!file) {
      setUploadFile(null);
      return;
    }

    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
    if (BLOCKED_EXTENSIONS.includes(ext)) {
      setUploadValidationError(`Files with extension "${ext}" are blocked for security.`);
      setUploadFile(null);
      return;
    }

    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadValidationError(`Invalid file type. Allowed extensions: ${ALLOWED_EXTENSIONS.join(', ')}`);
      setUploadFile(null);
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setUploadValidationError(`File size (${(file.size / (1024 * 1024)).toFixed(2)} MB) exceeds 5 MB limit.`);
      setUploadFile(null);
      return;
    }

    setUploadFile(file);
    if (!uploadDocName) {
      setUploadDocName(file.name.replace(/\.[^/.]+$/, ''));
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      setUploadValidationError("Please select a file to upload.");
      return;
    }
    if (!employee) return;

    setUploadSubmitting(true);
    setUploadValidationError(null);

    try {
      const formData = new FormData();
      formData.append('employee', employee.id.toString());
      formData.append('file', uploadFile);
      formData.append('document_type', uploadDocType);
      if (uploadDocName.trim()) {
        formData.append('document_name', uploadDocName.trim());
      }
      if (uploadDescription.trim()) {
        formData.append('description', uploadDescription.trim());
      }
      if (uploadExpiryDate) {
        formData.append('expiry_date', uploadExpiryDate);
      }

      await employeeDocumentService.uploadDocument(formData);
      setShowUploadModal(false);
      setUploadFile(null);
      setUploadDocName('');
      setUploadDescription('');
      setUploadExpiryDate('');
      await fetchDocuments();
    } catch (err: any) {
      const detail = err.data?.detail || err.data?.file?.[0] || 'Upload failed. Please check the file and try again.';
      setUploadValidationError(detail);
    } finally {
      setUploadSubmitting(false);
    }
  };

  const handleDelete = async (docId: number, docName: string) => {
    if (!window.confirm(`Are you sure you want to permanently delete "${docName}"?`)) return;
    setActionInProgress(docId);
    try {
      await employeeDocumentService.deleteDocument(docId);
      setDocuments(prev => prev.filter(d => d.id !== docId));
    } catch {
      alert("Failed to delete document. Ensure you have the required permissions.");
    } finally {
      setActionInProgress(null);
    }
  };

  const handleDownload = async (doc: EmployeeDocument) => {
    setActionInProgress(doc.id);
    try {
      await employeeDocumentService.downloadDocument(doc.id, doc.document_name);
    } catch {
      alert("Failed to download document.");
    } finally {
      setActionInProgress(null);
    }
  };

  const handlePreview = async (doc: EmployeeDocument) => {
    setActionInProgress(doc.id);
    try {
      await employeeDocumentService.previewDocument(doc.id);
    } catch {
      alert("Failed to preview document.");
    } finally {
      setActionInProgress(null);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
        <Loader2 className="animate-spin text-muted" size={40} />
      </div>
    );
  }

  if (error || !employee) {
    return (
      <div>
        <button className="btn btn-ghost" onClick={() => navigate('/admin/employees')} style={{ marginBottom: 'var(--spacing-md)' }}>
          <ArrowLeft size={16} /> Back to Directory
        </button>
        <Card>
          <EmptyState title="Error Loading Profile" description={error || "Profile not found."} icon={UserIcon} />
        </Card>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      {/* Top Action Bar */}
      <div>
        <button className="btn btn-ghost" onClick={() => navigate('/admin/employees')} style={{ padding: '4px 8px', marginLeft: '-8px' }}>
          <ArrowLeft size={16} /> Back to Directory
        </button>
      </div>

      {/* Header Card */}
      <Card style={{ padding: '0' }}>
        <div style={{ padding: 'var(--spacing-xl)', display: 'flex', alignItems: 'flex-start', gap: 'var(--spacing-xl)', flexWrap: 'wrap' }}>
          <div style={{ 
            width: '100px', height: '100px', borderRadius: 'var(--radius-lg)', 
            backgroundColor: 'var(--color-primary-light)', color: 'var(--color-primary)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '2rem', fontWeight: 600
          }}>
            {employee.first_name[0]}{employee.last_name[0]}
          </div>
          <div style={{ flex: 1, minWidth: '250px' }}>
            <h1 style={{ margin: '0 0 8px 0', fontSize: '1.75rem', fontWeight: 700 }}>
              {employee.first_name} {employee.last_name}
            </h1>
            <p style={{ margin: '0 0 12px 0', fontSize: '1rem', color: 'var(--color-text-muted)' }}>
              {employee.designation_name || 'No Designation'} &bull; {employee.department_name || 'No Department'}
            </p>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <StatusBadge status={(employee.employment_status || employee.status) as any} />
              <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Briefcase size={14} /> {employee.employee_code}
              </span>
            </div>
          </div>
        </div>
        
        {/* Tabs */}
        <div style={{ display: 'flex', borderTop: '1px solid var(--color-border)', padding: '0 var(--spacing-xl)', gap: '8px' }}>
          {(['overview', 'contact', 'employment', 'documents'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: activeTab === tab ? '2px solid var(--color-primary)' : '2px solid transparent',
                padding: '16px var(--spacing-md)',
                fontSize: '0.95rem',
                fontWeight: activeTab === tab ? 600 : 500,
                color: activeTab === tab ? 'var(--color-primary)' : 'var(--color-text-muted)',
                cursor: 'pointer',
                textTransform: 'capitalize',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {tab === 'documents' && <FileText size={16} />}
              {tab}
              {tab === 'documents' && documents.length > 0 && (
                <span style={{
                  fontSize: '0.75rem',
                  padding: '2px 6px',
                  borderRadius: '10px',
                  backgroundColor: activeTab === 'documents' ? 'var(--color-primary-light)' : 'var(--color-bg-subtle, #f1f5f9)',
                  color: activeTab === 'documents' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                }}>
                  {documents.length}
                </span>
              )}
            </button>
          ))}
        </div>
      </Card>

      {/* Tab Content */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--spacing-lg)' }}>
        {activeTab === 'overview' && (
          <>
            <Card title="Identity Information">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Full Name</span>
                  <span style={{ fontWeight: 500 }}>{employee.first_name} {employee.last_name}</span>
                </div>
                <div>
                  <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Employee Code</span>
                  <span style={{ fontWeight: 500 }}>{employee.employee_code}</span>
                </div>
                <div>
                  <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>System Account Status</span>
                  <StatusBadge status={employee.status as any} />
                </div>
              </div>
            </Card>

            <Card title="Organizational Information">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <Building size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Department</span>
                    <span style={{ fontWeight: 500 }}>{employee.department_name || '-'}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <Briefcase size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Designation</span>
                    <span style={{ fontWeight: 500 }}>{employee.designation_name || '-'}</span>
                  </div>
                </div>
              </div>
            </Card>
          </>
        )}

        {activeTab === 'contact' && (
          <Card title="Contact Information" style={{ gridColumn: '1 / -1' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                <Mail size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                <div>
                  <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Work Email</span>
                  <span style={{ fontWeight: 500 }}>{employee.email}</span>
                </div>
              </div>

              {employee.personal_email !== undefined ? (
                <>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                    <Mail size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                    <div>
                      <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Personal Email</span>
                      <span style={{ fontWeight: 500 }}>{employee.personal_email || '-'}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                    <Phone size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                    <div>
                      <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Phone Number</span>
                      <span style={{ fontWeight: 500 }}>{employee.phone_number || '-'}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                    <MapPin size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                    <div>
                      <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Address</span>
                      <span style={{ fontWeight: 500 }}>{employee.address || '-'}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div style={{ gridColumn: '1 / -1', padding: '16px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-md)' }}>
                  <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <UserIcon size={16} /> Sensitive contact information is restricted by your current role permissions.
                  </p>
                </div>
              )}
            </div>
            
            {employee.emergency_contact_name !== undefined && (
              <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid var(--color-border)' }}>
                <h3 style={{ fontSize: '1.05rem', margin: '0 0 16px 0' }}>Emergency Contact</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Name</span>
                    <span style={{ fontWeight: 500 }}>{employee.emergency_contact_name || '-'}</span>
                  </div>
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Phone</span>
                    <span style={{ fontWeight: 500 }}>{employee.emergency_contact_phone || '-'}</span>
                  </div>
                </div>
              </div>
            )}
          </Card>
        )}

        {activeTab === 'employment' && (
          <Card title="Employment Details" style={{ gridColumn: '1 / -1' }}>
             <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <Calendar size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Joining Date</span>
                    <span style={{ fontWeight: 500 }}>{employee.joining_date || '-'}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <Calendar size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Exit Date</span>
                    <span style={{ fontWeight: 500 }}>{employee.exit_date || '-'}</span>
                  </div>
                </div>
             </div>
          </Card>
        )}

        {activeTab === 'documents' && (
          <Card
            title="Employee Documents"
            style={{ gridColumn: '1 / -1' }}
            actions={
              canUploadDocs ? (
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setUploadValidationError(null);
                    setShowUploadModal(true);
                  }}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Upload size={16} /> Upload Document
                </button>
              ) : undefined
            }
          >
            {docsLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
                <Loader2 className="animate-spin text-muted" size={32} />
              </div>
            ) : docsError ? (
              <div style={{ padding: 'var(--spacing-lg)', textAlign: 'center' }}>
                <p style={{ color: 'var(--color-danger, #ef4444)', marginBottom: '12px' }}>{docsError}</p>
                <button className="btn btn-secondary" onClick={fetchDocuments}>Retry</button>
              </div>
            ) : documents.length === 0 ? (
              <EmptyState
                title="No Documents Uploaded"
                description="No employee documents have been attached to this profile yet."
                icon={FileText}
                action={
                  canUploadDocs ? (
                    <button
                      className="btn btn-primary"
                      onClick={() => {
                        setUploadValidationError(null);
                        setShowUploadModal(true);
                      }}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                    >
                      <Upload size={16} /> Upload First Document
                    </button>
                  ) : undefined
                }
              />
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}>
                      <th style={{ padding: '12px 16px', fontWeight: 600 }}>Name</th>
                      <th style={{ padding: '12px 16px', fontWeight: 600 }}>Type</th>
                      <th style={{ padding: '12px 16px', fontWeight: 600 }}>Size</th>
                      <th style={{ padding: '12px 16px', fontWeight: 600 }}>Uploaded By</th>
                      <th style={{ padding: '12px 16px', fontWeight: 600 }}>Date</th>
                      <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((doc) => (
                      <tr key={doc.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <td style={{ padding: '12px 16px', fontWeight: 500 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <FileText size={16} color="var(--color-primary)" />
                            <div>
                              <span>{doc.document_name}</span>
                              {doc.description && (
                                <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                                  {doc.description}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          <span style={{
                            fontSize: '0.75rem',
                            fontWeight: 500,
                            padding: '3px 8px',
                            borderRadius: '4px',
                            backgroundColor: 'var(--color-primary-light, #e0f2fe)',
                            color: 'var(--color-primary, #0284c7)',
                            textTransform: 'capitalize',
                          }}>
                            {doc.document_type_display || doc.document_type}
                          </span>
                        </td>
                        <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)' }}>
                          {formatFileSize(doc.file_size)}
                        </td>
                        <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
                          {doc.uploaded_by_email || '—'}
                        </td>
                        <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
                          {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                            {canViewDocs && (
                              <>
                                <button
                                  className="btn btn-ghost"
                                  onClick={() => handlePreview(doc)}
                                  disabled={actionInProgress === doc.id}
                                  title="Preview inline"
                                  style={{ padding: '6px' }}
                                >
                                  <Eye size={16} />
                                </button>
                                <button
                                  className="btn btn-ghost"
                                  onClick={() => handleDownload(doc)}
                                  disabled={actionInProgress === doc.id}
                                  title="Download file"
                                  style={{ padding: '6px' }}
                                >
                                  <Download size={16} />
                                </button>
                              </>
                            )}
                            {canDeleteDocs && (
                              <button
                                className="btn btn-ghost"
                                onClick={() => handleDelete(doc.id, doc.document_name)}
                                disabled={actionInProgress === doc.id}
                                title="Delete document"
                                style={{ padding: '6px', color: 'var(--color-danger, #ef4444)' }}
                              >
                                <Trash2 size={16} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )}
      </div>

      {/* Upload Document Modal */}
      {showUploadModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px',
        }}>
          <div style={{
            backgroundColor: 'var(--color-bg-surface, #ffffff)',
            borderRadius: 'var(--radius-lg, 12px)',
            maxWidth: '520px',
            width: '100%',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '16px 24px',
              borderBottom: '1px solid var(--color-border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>Upload Employee Document</h3>
              <button
                className="btn btn-ghost"
                onClick={() => setShowUploadModal(false)}
                disabled={uploadSubmitting}
                style={{ padding: '4px' }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {uploadValidationError && (
                <div style={{
                  padding: '12px',
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  borderRadius: 'var(--radius-md, 8px)',
                  color: 'var(--color-danger, #ef4444)',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}>
                  <AlertCircle size={16} style={{ flexShrink: 0 }} />
                  <span>{uploadValidationError}</span>
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
                  Document Type *
                </label>
                <select
                  value={uploadDocType}
                  onChange={(e) => setUploadDocType(e.target.value)}
                  disabled={uploadSubmitting}
                  className="input"
                  style={{ width: '100%' }}
                  required
                >
                  {DOCUMENT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
                  Document Title / Display Name
                </label>
                <input
                  type="text"
                  value={uploadDocName}
                  onChange={(e) => setUploadDocName(e.target.value)}
                  disabled={uploadSubmitting}
                  placeholder="e.g. Passport, Offer Letter, Degree"
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
                  File * (PDF, PNG, JPG, DOC, DOCX — Max 5 MB)
                </label>
                <input
                  type="file"
                  onChange={handleFileChange}
                  disabled={uploadSubmitting}
                  accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
                  Description (Optional)
                </label>
                <textarea
                  value={uploadDescription}
                  onChange={(e) => setUploadDescription(e.target.value)}
                  disabled={uploadSubmitting}
                  placeholder="Notes or details about this document"
                  className="input"
                  rows={2}
                  style={{ width: '100%', resize: 'vertical' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 500, marginBottom: '6px' }}>
                  Expiry Date (Optional)
                </label>
                <input
                  type="date"
                  value={uploadExpiryDate}
                  onChange={(e) => setUploadExpiryDate(e.target.value)}
                  disabled={uploadSubmitting}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setShowUploadModal(false)}
                  disabled={uploadSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={uploadSubmitting || !uploadFile}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  {uploadSubmitting ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}
                  {uploadSubmitting ? 'Uploading...' : 'Upload Document'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
