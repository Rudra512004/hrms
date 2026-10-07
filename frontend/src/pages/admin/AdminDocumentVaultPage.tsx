import React, { useState, useEffect } from 'react';
import { Download, Eye, FileText, Loader2, Plus, Mail } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { documentService, type IssuedDocument, type DocumentTemplateList } from '../../services/documents';
import { employeeManagementService } from '../../services/employeeManagement';
import type { EmployeeProfile } from '../../services/employee';

export const AdminDocumentVaultPage: React.FC = () => {
  const { hasPermission } = useAuth();
  
  const [documents, setDocuments] = useState<IssuedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Issue Modal
  const [showIssueModal, setShowIssueModal] = useState(false);
  const [templates, setTemplates] = useState<DocumentTemplateList[]>([]);
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  
  const [issueForm, setIssueForm] = useState({ template_id: '', employee_id: '' });
  const [issuing, setIssuing] = useState(false);
  const [viewingDoc, setViewingDoc] = useState<IssuedDocument | null>(null);

  useEffect(() => {
    fetchVault();
  }, []);

  const fetchVault = async () => {
    setLoading(true);
    try {
      const docs = await documentService.listIssuedDocuments();
      setDocuments(docs);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadDependenciesForIssue = async () => {
    if (templates.length === 0) {
      try {
        const [tpls, emps] = await Promise.all([
          documentService.listTemplates(),
          employeeManagementService.listEmployees()
        ]);
        setTemplates(tpls.filter(t => t.is_active && t.active_version));
        setEmployees(emps);
      } catch (err: any) {
        alert("Failed to load templates/employees: " + err.message);
      }
    }
  };

  const handleIssue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!issueForm.template_id || !issueForm.employee_id) return;
    setIssuing(true);
    try {
      const generated = await documentService.generateDocument({
        template_id: parseInt(issueForm.template_id),
        employee_id: parseInt(issueForm.employee_id)
      });
      setDocuments(prev => [generated, ...prev]);
      setShowIssueModal(false);
      setIssueForm({ template_id: '', employee_id: '' });
    } catch (err: any) {
      alert("Error generating document: " + err.message);
    } finally {
      setIssuing(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', color: 'var(--color-text-muted)' }}>
        <Loader2 size={32} style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  // HR has view_all usually, or any authenticated user can view their own
  // If the user can issue, they can see the 'Issue Document' button
  const canIssue = hasPermission('document.issue');

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)' }}>Document Vault</h1>
          <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>Secure repository of all issued letters and emails</p>
        </div>
        {canIssue && (
          <button
            onClick={() => { setShowIssueModal(true); loadDependenciesForIssue(); }}
            className="btn"
          >
            <Plus size={16} /> Issue Document
          </button>
        )}
      </div>

      {error && <div style={{ color: '#ef4444', marginBottom: '16px' }}>{error}</div>}

      {/* ISSUE MODAL */}
      {showIssueModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000
        }}>
          <div style={{ background: 'var(--color-bg-card)', padding: '24px', borderRadius: '12px', width: '400px', maxWidth: '90%', border: '1px solid var(--color-border)' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '1.2rem', color: 'var(--color-text-main)' }}>Issue Document</h3>
            <form onSubmit={handleIssue}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Select Template</label>
                <select
                  required
                  value={issueForm.template_id}
                  onChange={e => setIssueForm({...issueForm, template_id: e.target.value})}
                  style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-bg-body)', color: 'var(--color-text-main)' }}
                >
                  <option value="">-- Select Template --</option>
                  {templates.map(t => <option key={t.id} value={t.id}>{t.name} ({t.template_type.toUpperCase()})</option>)}
                </select>
              </div>
              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Select Employee</label>
                <select
                  required
                  value={issueForm.employee_id}
                  onChange={e => setIssueForm({...issueForm, employee_id: e.target.value})}
                  style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-bg-body)', color: 'var(--color-text-main)' }}
                >
                  <option value="">-- Select Employee --</option>
                  {employees.map(e => <option key={e.id} value={e.id}>{e.employee_code} - {e.first_name} {e.last_name}</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button type="button" onClick={() => setShowIssueModal(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" disabled={issuing} className="btn">
                  {issuing ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : 'Generate & Issue'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* VIEW MODAL (For HTML Emails) */}
      {viewingDoc && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000
        }}>
          <div style={{ background: 'var(--color-bg-card)', padding: '24px', borderRadius: '12px', width: '800px', maxWidth: '95%', maxHeight: '90vh', overflowY: 'auto', border: '1px solid var(--color-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--color-text-main)' }}>{viewingDoc.title}</h3>
              <button onClick={() => setViewingDoc(null)} className="btn btn-secondary" style={{ padding: '6px 12px' }}>Close</button>
            </div>
            <iframe
              title="Document Render"
              srcDoc={viewingDoc.body_snapshot}
              sandbox=""
              style={{ width: '100%', height: '400px', background: '#fff', borderRadius: '8px', border: '1px solid var(--color-border)' }}
            />
          </div>
        </div>
      )}

      {/* DOCUMENTS TABLE */}
      <div style={{ background: 'var(--color-bg-card)', borderRadius: '12px', border: '1px solid var(--color-border)', overflow: 'hidden' }}>
        {documents.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            <FileText size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
            <p>No documents found in the vault.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'var(--color-bg-body)', borderBottom: '1px solid var(--color-border)' }}>
                <th style={{ padding: '16px', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Document</th>
                <th style={{ padding: '16px', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Recipient</th>
                <th style={{ padding: '16px', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Type</th>
                <th style={{ padding: '16px', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Issued At</th>
                <th style={{ padding: '16px', fontWeight: 600, color: 'var(--color-text-muted)', fontSize: '0.85rem', textTransform: 'uppercase', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map(d => (
                <tr key={d.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '16px', color: 'var(--color-text-main)', fontWeight: 500 }}>{d.title}</td>
                  <td style={{ padding: '16px', color: 'var(--color-text-muted)' }}>{d.employee_name || d.candidate_name || 'Unknown'}</td>
                  <td style={{ padding: '16px' }}>
                    {d.document_type === 'email' ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'var(--color-bg-body)', padding: '4px 8px', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}><Mail size={14} /> Email</span>
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'var(--color-bg-body)', padding: '4px 8px', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}><FileText size={14} /> PDF</span>
                    )}
                  </td>
                  <td style={{ padding: '16px', color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>{new Date(d.issued_at).toLocaleString()}</td>
                  <td style={{ padding: '16px', textAlign: 'right' }}>
                    {d.document_type === 'pdf' && d.file_attachment ? (
                      <a href={d.file_attachment} target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                        <Download size={14} /> Download PDF
                      </a>
                    ) : d.document_type === 'email' ? (
                      <button onClick={() => setViewingDoc(d)} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                        <Eye size={14} /> View Render
                      </button>
                    ) : (
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>Unavailable</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
