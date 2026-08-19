export interface AttendanceRecord {
  id: number;
  employee: number;
  date: string;
  check_in: string | null;
  check_out: string | null;
  status: string;
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
  }
};
