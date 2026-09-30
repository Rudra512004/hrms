const base='/api/v1';
const headers=()=>({'Content-Type':'application/json',Authorization:`Token ${localStorage.getItem('auth_token')||''}`});
async function api<T>(path:string,init?:RequestInit):Promise<T>{const res=await fetch(`${base}${path}`,{...init,headers:{...headers(),...init?.headers}});if(!res.ok){const data=await res.json().catch(()=>({}));throw new Error(data.detail||'Request failed.')}return res.status===204?undefined as T:res.json();}
export type EmailSettings={sender_name:string;from_email:string;reply_to_email:string;automation_enabled:boolean};
export type EmailRule={id:number;name:string;event_type:string;recipient_mode:'event_recipient'|'organization_admins';is_active:boolean};
export type EmailTemplate={id:number;event_type:string;name:string;subject:string;body:string;is_active:boolean};
export type EmailDelivery={id:number;event_type:string;recipient_email:string;subject:string;status:string;error_message:string;created_at:string};
export const emailAutomation={settings:()=>api<EmailSettings>('/email-settings/current/'),saveSettings:(x:EmailSettings)=>api<EmailSettings>('/email-settings/current/',{method:'PATCH',body:JSON.stringify(x)}),test:(recipient_email:string)=>api<{status:string}>('/email-settings/test/',{method:'POST',body:JSON.stringify({recipient_email})}),rules:()=>api<EmailRule[]>('/email-rules/'),createRule:(x:Omit<EmailRule,'id'>)=>api<EmailRule>('/email-rules/',{method:'POST',body:JSON.stringify(x)}),templates:()=>api<EmailTemplate[]>('/email-templates/'),deliveries:()=>api<EmailDelivery[]>('/email-deliveries/')};
