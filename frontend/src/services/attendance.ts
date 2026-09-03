export interface AttendanceBreak {
  id: number;
  started_at: string;
  ended_at: string | null;
}

export interface AttendanceRecord {
  id: number;
  employee: number;
  date: string;
  check_in: string | null;
  check_out: string | null;
  status: string;
  total_break_duration: string | null;
  productive_work_duration: string | null;
  is_on_break: boolean;
  breaks: AttendanceBreak[];
}

export const attendanceService = {
  getHistory: async (): Promise<AttendanceRecord[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/attendance/', {
      headers: {
        'Authorization': `Token ${token}` 
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  checkIn: async (): Promise<AttendanceRecord> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/attendance/check-in/', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}` 
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  checkOut: async (): Promise<AttendanceRecord> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/attendance/check-out/', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}` 
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  startBreak: async (): Promise<AttendanceRecord> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/attendance/start-break/', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}` 
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  },

  endBreak: async (): Promise<AttendanceRecord> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('No authentication token');
    
    const response = await fetch('/api/v1/attendance/end-break/', {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}` 
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { response, errorData };
    }
    
    return await response.json();
  }
};
