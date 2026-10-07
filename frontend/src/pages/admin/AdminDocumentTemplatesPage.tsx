import React, { useState, useEffect } from 'react';
import { FileText, Plus, Loader2, Check, Mail, FileOutput, Play } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { documentService, type DocumentTemplateList, type DocumentTemplateDetail, type DocumentCategory } from '../../services/documents';

export const AdminDocumentTemplatesPage: React.FC = () => {
  const { hasPermission } = useAuth();
  
  const [templates, setTemplates] = useState<DocumentTemplateList[]>([]);
  const [categories, setCategories] = useState<DocumentCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Editor State
  const [editingTemplateId, setEditingTemplateId] = useState<number | null>(null);
  const [templateDetail, setTemplateDetail] = useState<DocumentTemplateDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  
  // Create Modal State
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', template_type: 'pdf' as 'pdf'|'email', category: '' });
  const [saving, setSaving] = useState(false);
  
  // Version Builder State
  const [newVersionForm, setNewVersionForm] = useState({ subject: '', body: '', is_published: true });
  const [savingVersion, setSavingVersion] = useState(false);

  // Preview State
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [tpls, cats] = await Promise.all([
        documentService.listTemplates(),
        documentService.listCategories()
      ]);
      setTemplates(tpls);
      setCategories(cats);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadTemplateDetail = async (id: number) => {
    setEditingTemplateId(id);
    setDetailLoading(true);
    setPreviewHtml(null);
    try {
      const detail = await documentService.getTemplate(id);
      setTemplateDetail(detail);
      if (detail.versions.length > 0) {
        const latest = detail.versions[0];
        setNewVersionForm({ subject: latest.subject, body: latest.body, is_published: true });
      } else {
        setNewVersionForm({ subject: '', body: '', is_published: true });
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const created = await documentService.createTemplate({
        name: form.name,
        template_type: form.template_type,
        category: form.category ? parseInt(form.category) : null,
      });
      setTemplates(prev => [created, ...prev]);
      setShowCreate(false);
      setForm({ name: '', template_type: 'pdf', category: '' });
      loadTemplateDetail(created.id);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTemplateId) return;
    setSavingVersion(true);
    try {
      await documentService.addVersion(editingTemplateId, newVersionForm);
      await loadTemplateDetail(editingTemplateId);
      // Update the main list to reflect potentially new active version
      const tpls = await documentService.listTemplates();
      setTemplates(tpls);
      alert('Version saved successfully!');
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSavingVersion(false);
    }
  };

  const handleActivateVersion = async (versionId: number) => {
    if (!editingTemplateId) return;
    try {
      await documentService.activateVersion(editingTemplateId, versionId);
      await loadTemplateDetail(editingTemplateId);
      const tpls = await documentService.listTemplates();
      setTemplates(tpls);
    } catch (err: any) {
      alert("Failed to activate version: " + err.message);
    }
  };

  const handlePreview = async () => {
    if (!editingTemplateId) return;
    setPreviewing(true);
    try {
      const res = await documentService.previewTemplate(editingTemplateId, {
        context_data: {
          employee: { first_name: 'Jane', last_name: 'Doe', code: 'EMP001', email: 'jane@example.com' },
          candidate: { first_name: 'John', last_name: 'Smith', full_name: 'John Smith', email: 'john@example.com' }
        }
      });
      setPreviewHtml(res.html);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setPreviewing(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', color: 'var(--color-text-muted)' }}>
        <Loader2 size={32} style={{ animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  if (!hasPermission('document.manage_templates')) {
    return <div style={{ padding: '24px', color: '#ef4444' }}>Permission Denied.</div>;
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
      
      {/* LEFT COLUMN - LISTING */}
      <div style={{ flex: '1 1 350px', minWidth: '350px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: 'var(--color-text-main)' }}>Document Templates</h1>
            <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>Manage PDFs & Emails</p>
          </div>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="btn"
          >
            <Plus size={16} /> New Template
          </button>
        </div>

        {error && <div style={{ color: '#ef4444', marginBottom: '16px' }}>{error}</div>}

        {showCreate && (
          <form onSubmit={handleCreate} style={{ background: 'var(--color-bg-card)', padding: '16px', borderRadius: '10px', border: '1px solid var(--color-border)', marginBottom: '16px' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: '1rem' }}>Create Template</h3>
            <input
              placeholder="Template Name"
              required
              value={form.name}
              onChange={e => setForm({...form, name: e.target.value})}
              style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--color-border)', marginBottom: '12px', background: 'var(--color-bg-body)', color: 'var(--color-text-main)' }}
            />
            <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
              <select
                value={form.template_type}
                onChange={e => setForm({...form, template_type: e.target.value as any})}
                style={{ flex: 1, padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--color-border)', background: 'var(--color-bg-body)', color: 'var(--color-text-main)' }}
              >
                <option value="pdf">PDF Document</option>
                <option value="email">Email Template</option>
              </select>
              <select
                value={form.category}
                onChange={e => setForm({...form, category: e.target.value})}
                style={{ flex: 1, padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--color-border)', background: 'var(--color-bg-body)', color: 'var(--color-text-main)' }}
              >
                <option value="">No Category</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button type="button" onClick={() => setShowCreate(false)} className="btn btn-secondary">Cancel</button>
              <button type="submit" disabled={saving} className="btn">
                {saving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Check size={14} />} Create
              </button>
            </div>
          </form>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {templates.length === 0 && <div style={{ padding: '20px', textAlign: 'center', color: 'var(--color-text-muted)', border: '1px dashed var(--color-border)', borderRadius: '10px' }}>No templates found.</div>}
          {templates.map(t => (
            <div
              key={t.id}
              onClick={() => loadTemplateDetail(t.id)}
              style={{
                padding: '12px 16px',
                borderRadius: '8px',
                border: `1px solid ${editingTemplateId === t.id ? 'var(--color-primary)' : 'var(--color-border)'}`,
                background: editingTemplateId === t.id ? 'var(--color-bg-body)' : 'var(--color-bg-card)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}
            >
              {t.template_type === 'email' ? <Mail size={18} style={{ color: 'var(--color-primary)' }} /> : <FileOutput size={18} style={{ color: 'var(--color-primary)' }} />}
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, color: 'var(--color-text-main)' }}>{t.name}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                  {t.category_name || 'Uncategorized'} • v{t.active_version || 0}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* RIGHT COLUMN - EDITOR */}
      <div style={{ flex: '2 1 500px', minWidth: '400px' }}>
        {detailLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '40px', color: 'var(--color-text-muted)' }}>
            <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
          </div>
        ) : templateDetail ? (
          <div style={{ background: 'var(--color-bg-card)', borderRadius: '10px', border: '1px solid var(--color-border)', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <h2 style={{ margin: 0, fontSize: '1.25rem', color: 'var(--color-text-main)' }}>{templateDetail.name}</h2>
                <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', background: 'var(--color-bg-body)', padding: '2px 8px', borderRadius: '99px', marginTop: '6px', display: 'inline-block' }}>
                  {templateDetail.template_type.toUpperCase()}
                </span>
              </div>
              <button onClick={handlePreview} disabled={previewing} className="btn btn-secondary">
                {previewing ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={14} />} Preview Active Version
              </button>
            </div>

            <div style={{ background: 'var(--color-bg-body)', padding: '12px', borderRadius: '8px', marginBottom: '20px', border: '1px solid var(--color-border)' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '8px' }}>AVAILABLE VARIABLES</div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {['{{ employee.first_name }}', '{{ employee.last_name }}', '{{ employee.code }}', '{{ employee.designation }}', '{{ candidate.first_name }}', '{{ candidate.full_name }}', '{{ candidate.designation }}'].map(v => (
                  <code key={v} style={{ background: 'var(--color-bg-card)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem', color: 'var(--color-primary)' }}>{v}</code>
                ))}
              </div>
            </div>

            {previewHtml ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h3 style={{ margin: 0, fontSize: '1rem' }}>Preview</h3>
                  <button onClick={() => setPreviewHtml(null)} className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem' }}>Close Preview</button>
                </div>
                <iframe
                  title="Template Preview"
                  srcDoc={previewHtml}
                  sandbox=""
                  style={{ width: '100%', height: '350px', background: '#fff', borderRadius: '8px', border: '1px solid var(--color-border)' }}
                />
              </div>
            ) : (
              <form onSubmit={handleSaveVersion}>
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Subject / Document Title</label>
                  <input
                    required
                    value={newVersionForm.subject}
                    onChange={e => setNewVersionForm({...newVersionForm, subject: e.target.value})}
                    style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-bg-body)', color: 'var(--color-text-main)' }}
                  />
                </div>
                <div style={{ marginBottom: '20px' }}>
                  <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Template Body (HTML)</label>
                  <textarea
                    required
                    value={newVersionForm.body}
                    onChange={e => setNewVersionForm({...newVersionForm, body: e.target.value})}
                    rows={15}
                    style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid var(--color-border)', background: 'var(--color-bg-body)', color: 'var(--color-text-main)', fontFamily: 'monospace', resize: 'vertical' }}
                  />
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', color: 'var(--color-text-main)' }}>
                    <input 
                      type="checkbox" 
                      checked={newVersionForm.is_published}
                      onChange={e => setNewVersionForm({...newVersionForm, is_published: e.target.checked})}
                    />
                    Publish immediately (Set as active)
                  </label>
                  <button type="submit" disabled={savingVersion} className="btn">
                    {savingVersion ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Check size={16} />} Save New Version
                  </button>
                </div>
              </form>
            )}

            {/* VERSION HISTORY */}
            {!previewHtml && templateDetail.versions.length > 0 && (
              <div style={{ marginTop: '32px', borderTop: '1px solid var(--color-border)', paddingTop: '20px' }}>
                <h3 style={{ margin: '0 0 16px', fontSize: '1rem', color: 'var(--color-text-main)' }}>Version History</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {templateDetail.versions.map(v => (
                    <div key={v.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: 'var(--color-bg-body)', borderRadius: '6px' }}>
                      <div>
                        <span style={{ fontWeight: 600, color: 'var(--color-text-main)', marginRight: '12px' }}>v{v.version_number}</span>
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>{new Date(v.created_at).toLocaleString()}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {v.is_published ? (
                          <span style={{ color: 'var(--color-beyondsure-green)', fontSize: '0.8rem', fontWeight: 600 }}>Active</span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleActivateVersion(v.id)}
                            className="btn btn-secondary"
                            style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                          >
                            Set Active
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--color-text-muted)', border: '1px dashed var(--color-border)', borderRadius: '10px' }}>
            <div style={{ textAlign: 'center' }}>
              <FileText size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
              <p>Select a template to view or edit</p>
            </div>
          </div>
        )}
      </div>

    </div>
  );
};
