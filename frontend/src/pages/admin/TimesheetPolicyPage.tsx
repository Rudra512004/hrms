import React,{useEffect,useState}from'react';
import {Settings2} from 'lucide-react';
import {AlertBanner} from '../../components/AlertBanner';
import {Card} from '../../components/Card';
import {PageHeader} from '../../components/PageHeader';
import {ts,type TimesheetPolicy} from '../../services/timesheets';

export const TimesheetPolicyPage:React.FC=()=>{
 const [policy,setPolicy]=useState<TimesheetPolicy|null>(null);const [error,setError]=useState<string|null>(null);const [saving,setSaving]=useState(false);
 useEffect(()=>{void ts.policy().then(setPolicy).catch(()=>setError('Unable to load the timesheet policy.'));},[]);
 const save=async(e:React.FormEvent)=>{e.preventDefault();if(!policy)return;setSaving(true);setError(null);try{setPolicy(await ts.updatePolicy(policy));}catch{setError('Unable to save the timesheet policy.');}finally{setSaving(false);}};
 if(!policy)return <div><PageHeader title="Timesheet Policy" subtitle="Configure organization-wide time-entry rules." />{error?<AlertBanner type="error" message={error}/>:<p>Loading policy…</p>}</div>;
 return <div><PageHeader title="Timesheet Policy" subtitle="These controls apply to future submissions without changing existing time records." />{error&&<AlertBanner type="error" message={error}/>}<Card><form onSubmit={save} style={{display:'grid',gap:18,maxWidth:620}}><div className="form-group"><label className="form-label">Submission cadence</label><select className="form-input" value={policy.cadence} onChange={e=>setPolicy({...policy,cadence:e.target.value as 'daily'|'weekly'})}><option value="daily">Daily</option><option value="weekly">Weekly</option></select></div><label><input type="checkbox" checked={policy.requires_manager_approval} onChange={e=>setPolicy({...policy,requires_manager_approval:e.target.checked})}/> Require manager approval before a timesheet is finalized</label><label><input type="checkbox" checked={policy.lock_on_submit} onChange={e=>setPolicy({...policy,lock_on_submit:e.target.checked})}/> Lock employee editing after submission</label><label><input type="checkbox" checked={policy.manager_can_reopen} onChange={e=>setPolicy({...policy,manager_can_reopen:e.target.checked})}/> Allow managers to reopen a submitted timesheet</label><button className="btn btn-primary" disabled={saving} type="submit"><Settings2 size={16}/>{saving?'Saving…':'Save Policy'}</button></form></Card></div>;
};
