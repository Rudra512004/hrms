export interface Announcement { id:number; organization:number; branch:number|null; branch_name?:string; title:string; body:string; is_published:boolean; published_at:string|null; expires_at:string|null; created_by_name:string; created_at:string; }
const headers=()=>({ 'Content-Type':'application/json', ...(localStorage.getItem('auth_token')?{Authorization:`Token ${localStorage.getItem('auth_token')}`}:{}) });
const response=async<T>(r:Response):Promise<T>=>{ if(!r.ok) throw new Error('Request failed'); return r.json(); };
export const announcementService={
  list:()=>fetch('/api/v1/announcements/',{headers:headers()}).then(response<Announcement[]>),
  create:(data:Partial<Announcement>)=>fetch('/api/v1/announcements/',{method:'POST',headers:headers(),body:JSON.stringify(data)}).then(response<Announcement>),
  update:(id:number,data:Partial<Announcement>)=>fetch(`/api/v1/announcements/${id}/`,{method:'PATCH',headers:headers(),body:JSON.stringify(data)}).then(response<Announcement>),
};
