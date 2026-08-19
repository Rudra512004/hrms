import React, { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { StatusBadge } from '../components/StatusBadge';
import { Loader2, Save, User as UserIcon, Building, ShieldAlert } from 'lucide-react';
import { employeeService, type EmployeeProfile } from '../services/employee';

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--spacing-xl)',
    maxWidth: '800px',
  },
  header: {
    marginBottom: 'var(--spacing-sm)',
  },
  title: {
    fontSize: '1.5rem',
    fontWeight: 700,
    color: 'var(--color-text-main)',
    margin: '0 0 var(--spacing-xs) 0',
  },
  subtitle: {
    color: 'var(--color-text-muted)',
    margin: 0,
    fontSize: '0.95rem',
  },
  section: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--spacing-md)',
  },
  sectionTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
    fontSize: '1.1rem',
    fontWeight: 600,
    color: 'var(--color-text-main)',
    margin: '0 0 var(--spacing-sm) 0',
    borderBottom: '1px solid var(--color-border)',
    paddingBottom: 'var(--spacing-sm)',
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px',
    marginBottom: 'var(--spacing-md)',
  },
  label: {
    fontSize: '0.85rem',
    fontWeight: 600,
    color: 'var(--color-text-main)',
  },
  input: {
    padding: '10px 14px',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.95rem',
    outline: 'none',
    transition: 'border-color 0.2s',
  },
  readOnlyValue: {
    padding: '10px 14px',
    backgroundColor: 'var(--color-bg-body)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.95rem',
    color: 'var(--color-text-muted)',
    cursor: 'not-allowed',
  },
  readOnlyBadge: {
    marginLeft: 'auto',
    fontSize: '0.7rem',
    backgroundColor: 'var(--color-bg-body)',
    padding: '2px 6px',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--color-text-muted)',
  },
  btnSave: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    backgroundColor: 'var(--color-primary)',
    color: '#fff',
    border: 'none',
    padding: '12px 24px',
    borderRadius: 'var(--radius-md)',
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background-color 0.2s',
    alignSelf: 'flex-start',
  },
  btnSaveDisabled: {
    backgroundColor: 'var(--color-text-muted)',
    cursor: 'not-allowed',
  },
  alert: (type: 'success' | 'error') => ({
    padding: 'var(--spacing-md)',
    borderRadius: 'var(--radius-md)',
    backgroundColor: type === 'success' ? 'var(--color-status-success)15' : 'var(--color-status-danger)15',
    color: type === 'success' ? 'var(--color-status-success)' : 'var(--color-status-danger)',
    border: `1px solid ${type === 'success' ? 'var(--color-status-success)30' : 'var(--color-status-danger)30'}`,
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
    marginBottom: 'var(--spacing-lg)',
  }),
  centerState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '400px',
    color: 'var(--color-text-muted)',
  }
};

export const ProfilePage: React.FC = () => {
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  // Editable form state
  const [formData, setFormData] = useState({
    phone_number: '',
    address: '',
    emergency_contact_name: '',
    emergency_contact_phone: ''
  });

  useEffect(() => {
    employeeService.getProfile()
      .then(p => {
        setProfile(p);
        setFormData({
          phone_number: p.phone_number || '',
          address: p.address || '',
          emergency_contact_name: p.emergency_contact_name || '',
          emergency_contact_phone: p.emergency_contact_phone || ''
        });
      })
      .catch(err => {
        if (err.message === 'Failed to fetch profile' || err.status === 403) {
           setError("You do not have access to view this profile or your session expired.");
        } else {
           setError("An unexpected error occurred loading your profile.");
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setSaveError(null);
    setSaveSuccess(false);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      const updatedProfile = await employeeService.updateProfile(formData);
      setProfile(updatedProfile);
      setFormData({
        phone_number: updatedProfile.phone_number || '',
        address: updatedProfile.address || '',
        emergency_contact_name: updatedProfile.emergency_contact_name || '',
        emergency_contact_phone: updatedProfile.emergency_contact_phone || ''
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      if (err.errorData) {
        // Find the first field error or non_field_errors
        const errors = err.errorData;
        const firstErrorKey = Object.keys(errors)[0];
        if (firstErrorKey) {
          setSaveError(`${firstErrorKey}: ${errors[firstErrorKey][0]}`);
        } else {
          setSaveError('Failed to save profile. Please check your inputs.');
        }
      } else {
        setSaveError('A network error occurred while saving.');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.centerState}>
        <Loader2 size={32} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite', marginBottom: 'var(--spacing-md)' }} />
        <p>Loading profile...</p>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div style={styles.centerState}>
        <ShieldAlert size={48} color="var(--color-status-danger)" style={{ marginBottom: 'var(--spacing-md)' }} />
        <h3 style={{ color: 'var(--color-text-main)', marginBottom: 'var(--spacing-xs)' }}>Access Denied</h3>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>My Profile</h1>
        <p style={styles.subtitle}>Manage your personal and contact information.</p>
      </div>

      {saveSuccess && (
        <div style={styles.alert('success')}>
          <span>Your profile has been successfully updated.</span>
        </div>
      )}

      {saveError && (
        <div style={styles.alert('error')}>
          <span>{saveError}</span>
        </div>
      )}

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xl)' }}>
        <Card>
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}><UserIcon size={20} /> Identity Summary</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-lg)' }}>
              <div style={styles.formGroup}>
                <label style={styles.label}>First Name</label>
                <div style={styles.readOnlyValue}>{profile.first_name}</div>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Last Name</label>
                <div style={styles.readOnlyValue}>{profile.last_name}</div>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <Building size={20} /> Company Information
              <span style={styles.readOnlyBadge}>HR CONTROLLED</span>
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-lg)' }}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Company Email</label>
                <div style={styles.readOnlyValue}>{profile.email}</div>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Employee Code</label>
                <div style={styles.readOnlyValue}>{profile.employee_code}</div>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Account Status</label>
                <div style={{ marginTop: '8px' }}>
                  <StatusBadge status={profile.status as any} />
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>Personal Information</h2>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-lg)' }}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Phone Number</label>
                <input
                  type="text"
                  name="phone_number"
                  value={formData.phone_number}
                  onChange={handleChange}
                  style={styles.input}
                  placeholder="+1234567890"
                />
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Address</label>
              <textarea
                name="address"
                value={formData.address}
                onChange={handleChange}
                style={{ ...styles.input, minHeight: '80px', resize: 'vertical' }}
                placeholder="123 Main St, City, Country"
              />
            </div>
            
            <div style={{ marginTop: 'var(--spacing-md)' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: 'var(--spacing-md)', color: 'var(--color-text-main)' }}>Emergency Contact</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-lg)' }}>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Contact Name</label>
                  <input
                    type="text"
                    name="emergency_contact_name"
                    value={formData.emergency_contact_name}
                    onChange={handleChange}
                    style={styles.input}
                    placeholder="Jane Doe"
                  />
                </div>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Contact Phone</label>
                  <input
                    type="text"
                    name="emergency_contact_phone"
                    value={formData.emergency_contact_phone}
                    onChange={handleChange}
                    style={styles.input}
                    placeholder="+1234567890"
                  />
                </div>
              </div>
            </div>
          </div>
        </Card>

        <button 
          type="submit" 
          disabled={saving} 
          style={{ ...styles.btnSave, ...(saving ? styles.btnSaveDisabled : {}) }}
        >
          {saving ? <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={20} />}
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </form>
    </div>
  );
};
