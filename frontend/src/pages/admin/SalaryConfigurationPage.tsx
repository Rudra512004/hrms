import React, { useCallback, useEffect, useState } from 'react';
import { PlusCircle, ReceiptText, Settings2, Trash2 } from 'lucide-react';
import { AlertBanner } from '../../components/AlertBanner';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { Modal } from '../../components/Modal';
import { PageHeader } from '../../components/PageHeader';
import {
  salaryConfigurationService,
  type SalaryComponent,
  type SalaryStructure,
} from '../../services/salaryConfiguration';

const money = (value: string) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(value));

export const SalaryConfigurationPage: React.FC = () => {
  const [components, setComponents] = useState<SalaryComponent[]>([]);
  const [structures, setStructures] = useState<SalaryStructure[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [componentModal, setComponentModal] = useState(false);
  const [structureModal, setStructureModal] = useState(false);
  const [selectedStructure, setSelectedStructure] = useState<SalaryStructure | null>(null);
  const [componentForm, setComponentForm] = useState({ name: '', code: '', kind: 'earning' as 'earning' | 'deduction', is_taxable: false });
  const [structureName, setStructureName] = useState('');
  const [lineComponent, setLineComponent] = useState('');
  const [lineAmount, setLineAmount] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [componentData, structureData] = await Promise.all([
        salaryConfigurationService.getComponents(), salaryConfigurationService.getStructures(),
      ]);
      setComponents(componentData); setStructures(structureData);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not load salary configuration.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const createComponent = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await salaryConfigurationService.createComponent({ ...componentForm, is_active: true });
      setComponentModal(false); setComponentForm({ name: '', code: '', kind: 'earning', is_taxable: false }); await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not create salary component.'); }
  };
  const createStructure = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await salaryConfigurationService.createStructure({ name: structureName, is_active: true });
      setStructureModal(false); setStructureName(''); await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not create salary structure.'); }
  };
  const addLine = async (event: React.FormEvent) => {
    event.preventDefault(); if (!selectedStructure || !lineComponent || !lineAmount) return;
    try {
      await salaryConfigurationService.setStructureComponent(selectedStructure.id, Number(lineComponent), lineAmount);
      setLineComponent(''); setLineAmount(''); await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not update structure.'); }
  };
  const removeLine = async (componentId: number) => {
    if (!selectedStructure) return;
    try { await salaryConfigurationService.removeStructureComponent(selectedStructure.id, componentId); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not remove component.'); }
  };
  const liveSelected = selectedStructure ? structures.find(s => s.id === selectedStructure.id) || null : null;

  return <div>
    <PageHeader title="Salary Configuration" subtitle="Define reusable earning, deduction and salary-structure building blocks." />
    {error && <AlertBanner type="error" message={error} />}
    <div className="page-actions" style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
      <button className="btn btn-secondary" onClick={() => setComponentModal(true)}><PlusCircle size={16} /> Add Component</button>
      <button className="btn btn-primary" onClick={() => setStructureModal(true)}><PlusCircle size={16} /> Add Structure</button>
    </div>
    <div className="control-center-grid">
      <Card><div className="card-header"><h3><ReceiptText size={18} /> Salary Components</h3></div>
        {loading ? <p>Loading configuration…</p> : components.length === 0 ? <EmptyState icon={ReceiptText} title="No salary components" description="Add earnings and deductions to build salary structures." /> :
          <div className="table-responsive"><table className="data-table"><thead><tr><th>Name</th><th>Code</th><th>Type</th><th>Taxable</th><th>Status</th></tr></thead><tbody>{components.map(c => <tr key={c.id}><td>{c.name}</td><td><code>{c.code}</code></td><td>{c.kind}</td><td>{c.is_taxable ? 'Yes' : 'No'}</td><td>{c.is_active ? 'Active' : 'Inactive'}</td></tr>)}</tbody></table></div>}
      </Card>
      <Card><div className="card-header"><h3><Settings2 size={18} /> Salary Structures</h3></div>
        {loading ? <p>Loading configuration…</p> : structures.length === 0 ? <EmptyState icon={Settings2} title="No salary structures" description="Create a structure and assign the reusable components." /> :
          <div className="table-responsive"><table className="data-table"><thead><tr><th>Structure</th><th>Earnings</th><th>Deductions</th><th></th></tr></thead><tbody>{structures.map(s => <tr key={s.id}><td>{s.name}</td><td>{money(s.monthly_earnings)}</td><td>{money(s.monthly_deductions)}</td><td><button className="btn btn-secondary btn-sm" onClick={() => setSelectedStructure(s)}>Configure</button></td></tr>)}</tbody></table></div>}
      </Card>
    </div>
    {componentModal && <Modal title="Add Salary Component" onClose={() => setComponentModal(false)}><form onSubmit={createComponent} className="form-grid"><div className="form-group"><label className="form-label">Name</label><input className="form-input" required value={componentForm.name} onChange={e => setComponentForm({ ...componentForm, name: e.target.value })} /></div><div className="form-group"><label className="form-label">Code</label><input className="form-input" required value={componentForm.code} onChange={e => setComponentForm({ ...componentForm, code: e.target.value })} /></div><div className="form-group"><label className="form-label">Type</label><select className="form-input" value={componentForm.kind} onChange={e => setComponentForm({ ...componentForm, kind: e.target.value as 'earning' | 'deduction' })}><option value="earning">Earning</option><option value="deduction">Deduction</option></select></div><label><input type="checkbox" checked={componentForm.is_taxable} onChange={e => setComponentForm({ ...componentForm, is_taxable: e.target.checked })} /> Taxable component</label><button className="btn btn-primary" type="submit">Save Component</button></form></Modal>}
    {structureModal && <Modal title="Add Salary Structure" onClose={() => setStructureModal(false)}><form onSubmit={createStructure} className="form-grid"><div className="form-group"><label className="form-label">Name</label><input className="form-input" required value={structureName} onChange={e => setStructureName(e.target.value)} /></div><button className="btn btn-primary" type="submit">Save Structure</button></form></Modal>}
    {liveSelected && <Modal title={`Configure ${liveSelected.name}`} onClose={() => setSelectedStructure(null)} size="lg"><form onSubmit={addLine} style={{ display: 'flex', gap: 8, marginBottom: 18 }}><select className="form-input" required value={lineComponent} onChange={e => setLineComponent(e.target.value)}><option value="">Choose component</option>{components.filter(c => c.is_active).map(c => <option key={c.id} value={c.id}>{c.name} ({c.code})</option>)}</select><input className="form-input" required min="0" type="number" step="0.01" placeholder="Monthly amount" value={lineAmount} onChange={e => setLineAmount(e.target.value)} /><button className="btn btn-primary" type="submit">Set</button></form><div className="table-responsive"><table className="data-table"><thead><tr><th>Component</th><th>Type</th><th>Monthly amount</th><th></th></tr></thead><tbody>{liveSelected.components.map(line => <tr key={line.id}><td>{line.component_name} <code>{line.component_code}</code></td><td>{line.component_kind}</td><td>{money(line.amount)}</td><td><button className="icon-btn" aria-label={`Remove ${line.component_name}`} onClick={() => void removeLine(line.component)}><Trash2 size={15} /></button></td></tr>)}</tbody></table></div></Modal>}
  </div>;
};
