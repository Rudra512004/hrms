import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { authService, type User, type AuthSession } from '../services/auth';


interface AuthContextType {
  user: User | null;
  roles: string[];
  permissions: string[];
  loading: boolean;
  error: string | null;
  hasPermission: (permission: string) => boolean;
  refreshAuth: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const loadAuth = async () => {
    setLoading(true);
    setError(null);
    try {
      const currentSession = await authService.getCurrentUser();
      if (currentSession) {
        setSession(currentSession);
      } else {
        setSession(null);
      }
    } catch (err: any) {
      console.error('Failed to load auth state:', err);
      setError(err.message || 'Authentication failed');
      setSession(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuth();
    
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'auth_token') {
        loadAuth();
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const hasPermission = (permission: string): boolean => {
    if (!session || !session.permissions) return false;
    return session.permissions.includes(permission);
  };

  const logout = async () => {
    await authService.logout();
    setSession(null);
  };

  return (
    <AuthContext.Provider 
      value={{ 
        user: session?.user || null, 
        roles: session?.roles || [], 
        permissions: session?.permissions || [], 
        loading, 
        error, 
        hasPermission,
        refreshAuth: loadAuth,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
