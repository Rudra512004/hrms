const h=()=>({'Content-Type':'application/json',...(localStorage.getItem('auth_token')?{Authorization:`Token ${localStorage.getItem('auth_token')}`}:{})});
const j=async<T>(r:Response):Promise<T>=>{if(!r.ok){const body=await r.text();throw Error(body||'Request failed')}return r.json()};

export type Cycle={id:number;name:string;start_date:string;end_date:string;is_active:boolean};
export type Review={id:number;employee:number;employee_name:string;reviewer:number|null;reviewer_name:string|null;rating:number|null;summary:string;status:string;cycle:number};

export const reviews={
    cycles:()=>fetch('/api/v1/employees/review-cycles/',{headers:h()}).then(j<Cycle[]>),
    addCycle:(x:Partial<Cycle>)=>fetch('/api/v1/employees/review-cycles/',{method:'POST',headers:h(),body:JSON.stringify(x)}).then(j<Cycle>),
    list:()=>fetch('/api/v1/employees/reviews/',{headers:h()}).then(j<Review[]>),
    mine:()=>fetch('/api/v1/employees/reviews/',{headers:h()}).then(j<Review[]>),
    create:(x:{cycle:number,employee:number,rating?:number,summary?:string})=>fetch('/api/v1/employees/reviews/',{method:'POST',headers:h(),body:JSON.stringify(x)}).then(j<Review>),
    submit:(id:number)=>fetch(`/api/v1/employees/reviews/${id}/submit/`,{method:'POST',headers:h()}).then(j<Review>),
    ack:(id:number)=>fetch(`/api/v1/employees/reviews/${id}/acknowledge/`,{method:'POST',headers:h()}).then(j<Review>)
};
