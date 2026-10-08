const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    'Authorization': token ? `Token ${token}` : '',
  };
};

export const allowanceService = {
  getAllowanceTypes: async () => {
    const res = await fetch('/api/v1/allowances/types/', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch allowance types');
    const data = await res.json();
    return data.results || data;
  },
  
  getEmployeeAllowances: async () => {
    const res = await fetch('/api/v1/allowances/assignments/', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch employee allowances');
    const data = await res.json();
    return data.results || data;
  },

  getMyAllowances: async () => {
    const res = await fetch('/api/v1/allowances/assignments/my_allowances/', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch my allowances');
    const data = await res.json();
    return data.results || data;
  },

  getReimbursementClaims: async () => {
    const res = await fetch('/api/v1/allowances/claims/', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch reimbursement claims');
    const data = await res.json();
    return data.results || data;
  },

  getMyReimbursements: async () => {
    const res = await fetch('/api/v1/allowances/claims/my_claims/', {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch my reimbursements');
    const data = await res.json();
    return data.results || data;
  },

  approveReimbursement: async (id: string, reviewer_comments: string) => {
    const res = await fetch(`/api/v1/allowances/claims/${id}/approve/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ reviewer_comments }),
    });
    if (!res.ok) throw new Error('Failed to approve reimbursement claim');
    return await res.json();
  },

  rejectReimbursement: async (id: string, reviewer_comments: string) => {
    const res = await fetch(`/api/v1/allowances/claims/${id}/reject/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ reviewer_comments }),
    });
    if (!res.ok) throw new Error('Failed to reject reimbursement claim');
    return await res.json();
  }
};
