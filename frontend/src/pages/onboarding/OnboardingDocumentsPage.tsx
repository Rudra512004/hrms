/**
 * Candidate onboarding — document upload and management.
 */
import React, { useState, useEffect, useRef } from 'react';
import { Upload, Trash2, AlertCircle, Loader2, XCircle, FileText } from 'lucide-react';
import { candidatePortalService, type CandidateDocument } from '../../services/candidates';

const DOC_TYPES = [
  { value: 'identity',   label: 'Identity Proof' },
  { value: 'address',    label: 'Address Proof' },
  { value: 'education',  label: 'Education Certificate' },
  { value: 'employment', label: 'Previous Employment Proof' },
  { value: 'other',      label: 'Other' },
];

function DocStatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { bg: string; color: string; label: string }> = {
    pending:  { bg: '#fffbeb', color: '#f59e0b', label: 'Pending' },
    verified: { bg: '#f0fdf4', color: 'var(--color-beyondsure-green)', label: 'Verified' },
    rejected: { bg: '#fef2f2', color: '#ef4444', label: 'Rejected' },
  };
  const c = cfg[status] || cfg.pending;
  return (
    <span style={{ padding: '3px 10px', borderRadius: '99px', fontSize: '0.75rem', fontWeight: 600, background: c.bg, color: c.color }}>
      {c.label}
    </span>
  );
}

export const OnboardingDocumentsPage: React.FC = () => {
  const [docs, setDocs] = useState<CandidateDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [docType, setDocType] = useState('identity');
  const [description, setDescription] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    setLoading(true);
    candidatePortalService.getDocuments()
      .then(setDocs)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploadError('');
    setUploading(true);

    const fd = new FormData();
    fd.append('file', file);
    fd.append('document_type', docType);
    if (description) fd.append('description', description);

    try {
      const doc = await candidatePortalService.uploadDocument(fd);
      setDocs(prev => [doc, ...prev]);
      if (fileRef.current) fileRef.current.value = '';
      setDescription('');
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    setUploadError('');
    if (!window.confirm('Delete this document?')) return;
    try {
      await candidatePortalService.deleteDocument(id);
      setDocs(prev => prev.filter(d => d.id !== id));
    } catch (err: any) {
      setUploadError(err.message || 'Delete failed.');
    }
  };

  return (
    <div style={{ maxWidth: '800px' }}>
      <h1 style={{ margin: '0 0 4px', fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
        Documents
      </h1>
      <p style={{ margin: '0 0 24px', color: 'var(--color-text-muted)' }}>
        Upload your onboarding documents. Accepted formats: PDF, PNG, JPG, JPEG, DOC, DOCX (max 5 MB each).
      </p>

      {/* Upload form */}
      <div style={{
        background: 'var(--color-bg-card)', borderRadius: '12px',
        border: '1px solid var(--color-border)', padding: '20px', marginBottom: '24px',
      }}>
        <h2 style={{ margin: '0 0 16px', fontSize: '1rem', fontWeight: 600 }}>Upload Document</h2>
        <form onSubmit={handleUpload}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Document Type
              </label>
              <select
                value={docType}
                onChange={e => setDocType(e.target.value)}
                style={{
                  width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
                  borderRadius: '8px', background: 'var(--color-bg-body)',
                  color: 'var(--color-text-main)', fontSize: '0.9rem', boxSizing: 'border-box',
                }}
              >
                {DOC_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                File <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                type="file"
                ref={fileRef}
                required
                accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                style={{
                  width: '100%', padding: '7px 12px', border: '1px solid var(--color-border)',
                  borderRadius: '8px', background: 'var(--color-bg-body)',
                  color: 'var(--color-text-main)', fontSize: '0.875rem', boxSizing: 'border-box',
                }}
              />
            </div>
          </div>
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
              Description (optional)
            </label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="e.g. Aadhaar Card front page"
              style={{
                width: '100%', padding: '9px 12px', border: '1px solid var(--color-border)',
                borderRadius: '8px', background: 'var(--color-bg-body)',
                color: 'var(--color-text-main)', fontSize: '0.9rem', boxSizing: 'border-box',
              }}
            />
          </div>

          {uploadError && (
            <div style={{ display: 'flex', gap: '8px', color: '#ef4444', marginBottom: '12px', fontSize: '0.875rem' }}>
              <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '1px' }} /> {uploadError}
            </div>
          )}

          <button
            type="submit"
            disabled={uploading}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '9px 18px', border: 'none', borderRadius: '8px',
              background: 'var(--color-primary)', color: '#fff',
              cursor: uploading ? 'not-allowed' : 'pointer', fontWeight: 600,
              opacity: uploading ? 0.7 : 1,
            }}
          >
            {uploading ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Upload size={14} />}
            {uploading ? 'Uploading…' : 'Upload Document'}
          </button>
        </form>
      </div>

      {/* Doc list */}
      <div>
        <h2 style={{ margin: '0 0 14px', fontSize: '1rem', fontWeight: 600, color: 'var(--color-text-main)' }}>
          Uploaded Documents ({docs.length})
        </h2>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--color-text-muted)' }}>
            <Loader2 size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: '8px' }} />
          </div>
        ) : error ? (
          <div style={{ color: '#ef4444' }}>{error}</div>
        ) : docs.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: '40px',
            border: '2px dashed var(--color-border)', borderRadius: '12px',
            color: 'var(--color-text-muted)',
          }}>
            <FileText size={36} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <p style={{ margin: 0 }}>No documents uploaded yet.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {docs.map(doc => (
              <div key={doc.id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '14px', border: '1px solid var(--color-border)',
                borderRadius: '10px', background: 'var(--color-bg-card)',
                flexWrap: 'wrap', gap: '10px',
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {doc.document_name}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                    {doc.document_type_display} · {(doc.file_size / 1024).toFixed(0)} KB
                  </div>
                  {doc.description && (
                    <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                      {doc.description}
                    </div>
                  )}
                  {doc.rejection_reason && (
                    <div style={{ fontSize: '0.78rem', color: '#ef4444', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <XCircle size={12} /> {doc.rejection_reason}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <DocStatusBadge status={doc.status} />
                  {doc.status === 'pending' && (
                    <button
                      onClick={() => handleDelete(doc.id)}
                      title="Delete document"
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        width: '30px', height: '30px', border: 'none', borderRadius: '6px',
                        background: '#fef2f2', color: '#ef4444', cursor: 'pointer',
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
