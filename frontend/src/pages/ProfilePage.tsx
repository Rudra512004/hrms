import React, { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { StatusBadge } from '../components/StatusBadge';
import { Loader2, Save, User as UserIcon, Building, ShieldAlert, Lock, KeyRound, CheckCircle2 } from 'lucide-react';
import { employeeService, type EmployeeProfile } from '../services/employee';
import { authService } from '../services/auth';
import { useAuth } from '../contexts/AuthContext';

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
  readOnlyValue: {
    padding: '10px 14px',
    backgroundColor: 'var(--color-bg-body)',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.95rem',
    color: 'var(--color-text-muted)',
    cursor: 'not-allowed',
    boxShadow: 'var(--shadow-inset)',
  },
  readOnlyBadge: {
    marginLeft: 'auto',
    fontSize: '0.7rem',
    backgroundColor: 'var(--color-bg-body)',
    padding: '2px 6px',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--color-text-muted)',
    boxShadow: 'var(--shadow-inset)',
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
  const { hasPermission, hasEmployeeProfile, user, refreshAuth } = useAuth();
  const canEditAll = hasPermission('employee.update');
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  // Editable form state
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    personal_email: '',
    phone_number: '',
    address: '',
    emergency_contact_name: '',
    emergency_contact_phone: ''
  });

  // Password change state
  const [passwordData, setPasswordData] = useState({
    old_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!passwordData.old_password || !passwordData.new_password || !passwordData.confirm_password) {
      setPasswordError('Please fill in all password fields.');
      return;
    }

    if (passwordData.new_password !== passwordData.confirm_password) {
      setPasswordError('New password and confirmation do not match.');
      return;
    }

    if (passwordData.new_password.length < 8) {
      setPasswordError('New password must be at least 8 characters long.');
      return;
    }

    try {
      setPasswordSaving(true);
      const msg = await authService.changePassword(
        passwordData.old_password,
        passwordData.new_password,
        passwordData.confirm_password
      );
      setPasswordSuccess(msg || 'Password changed successfully.');
      setPasswordData({ old_password: '', new_password: '', confirm_password: '' });
      setTimeout(() => setPasswordSuccess(null), 4000);
    } catch (err: any) {
      setPasswordError(err.message || 'Failed to change password. Please check your credentials.');
    } finally {
      setPasswordSaving(false);
    }
  };


  useEffect(() => {
    if (!hasEmployeeProfile) {
      setFormData((current) => ({
        ...current,
        first_name: user?.firstName || '',
        last_name: user?.lastName || '',
        email: user?.email || '',
      }));
      setLoading(false);
      return;
    }

    employeeService.getProfile()
      .then((p) => {
        setProfile(p);
        setFormData({
          first_name: p.first_name || '',
          last_name: p.last_name || '',
          email: p.email || '',
          personal_email: p.personal_email || '',
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
  }, [hasEmployeeProfile, user]);

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
      if (!hasEmployeeProfile) {
        await authService.updateAccountProfile({
          first_name: formData.first_name,
          last_name: formData.last_name,
        });
        await refreshAuth();
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
        return;
      }
      const updatedProfile = await employeeService.updateProfile(formData);
      setProfile(updatedProfile);
      setFormData({
        first_name: updatedProfile.first_name || '',
        last_name: updatedProfile.last_name || '',
        email: updatedProfile.email || '',
        personal_email: updatedProfile.personal_email || '',
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

  if (error || (hasEmployeeProfile && !profile)) {
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
                {hasEmployeeProfile ? (
                  canEditAll ? (
                    <input type="text" name="first_name" value={formData.first_name} onChange={handleChange} className="input-neumorphic" />
                  ) : (
                    <div style={styles.readOnlyValue}>{profile?.first_name}</div>
                  )
                ) : <input type="text" name="first_name" value={formData.first_name} onChange={handleChange} className="input-neumorphic" required />}
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Last Name</label>
                {hasEmployeeProfile ? (
                  canEditAll ? (
                    <input type="text" name="last_name" value={formData.last_name} onChange={handleChange} className="input-neumorphic" />
                  ) : (
                    <div style={styles.readOnlyValue}>{profile?.last_name}</div>
                  )
                ) : <input type="text" name="last_name" value={formData.last_name} onChange={handleChange} className="input-neumorphic" required />}
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <Building size={20} /> Company Information
              {!canEditAll && hasEmployeeProfile && <span style={styles.readOnlyBadge}>HR CONTROLLED</span>}
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-lg)' }}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Company Email</label>
                {hasEmployeeProfile ? (
                  canEditAll ? (
                    <input type="email" name="email" value={formData.email} onChange={handleChange} className="input-neumorphic" />
                  ) : (
                    <div style={styles.readOnlyValue}>{profile?.email}</div>
                  )
                ) : (
                  <div style={styles.readOnlyValue}>{user?.email || '—'}</div>
                )}
              </div>
              {hasEmployeeProfile && (
                <>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Employee Code</label>
                    <div style={styles.readOnlyValue}>{profile?.employee_code}</div>
                  </div>
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Account Status</label>
                    <div style={{ marginTop: '8px' }}>
                      <StatusBadge status={profile?.status as any} />
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </Card>

        {hasEmployeeProfile && (
          <Card>
            <div style={styles.section}>
              <h2 style={styles.sectionTitle}>Personal Information</h2>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-lg)' }}>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Personal Email</label>
                  {canEditAll ? (
                    <input type="email" name="personal_email" value={formData.personal_email} onChange={handleChange} className="input-neumorphic" />
                  ) : (
                    <div style={styles.readOnlyValue}>{profile?.personal_email || 'Not provided'}</div>
                  )}
                </div>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Phone Number</label>
                  <input
                    type="text"
                    name="phone_number"
                    value={formData.phone_number}
                    onChange={handleChange}
                    className="input-neumorphic"
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
                  className="input-neumorphic"
                  style={{ minHeight: '80px', resize: 'vertical' }}
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
                      className="input-neumorphic"
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
                      className="input-neumorphic"
                      placeholder="+1234567890"
                    />
                  </div>
                </div>
              </div>
            </div>
          </Card>
        )}

        {(hasEmployeeProfile || user?.isSuperuser) && (
          <button
            type="submit"
            disabled={saving}
            className="btn btn-primary"
            style={{ alignSelf: 'flex-start' }}
          >
            {saving ? <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={20} />}
            {saving ? 'Saving...' : hasEmployeeProfile ? 'Save Changes' : 'Save Account Profile'}
          </button>
        )}
      </form>

      {/* Account Security & Password */}
      <Card>
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>
            <Lock size={20} /> Account Security & Password
          </h2>
          <p style={{ margin: '0 0 var(--spacing-md) 0', fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
            Update your account password. Choose a strong, unique password with at least 8 characters.
          </p>

          {passwordError && (
            <div style={styles.alert('error')}>
              <ShieldAlert size={18} />
              <span>{passwordError}</span>
            </div>
          )}

          {passwordSuccess && (
            <div style={styles.alert('success')}>
              <CheckCircle2 size={18} />
              <span>{passwordSuccess}</span>
            </div>
          )}

          <form onSubmit={handlePasswordChange}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: 'var(--spacing-md)',
                marginBottom: 'var(--spacing-md)',
              }}
            >
              <div style={styles.formGroup}>
                <label style={styles.label}>Current Password</label>
                <input
                  type="password"
                  name="old_password"
                  value={passwordData.old_password}
                  onChange={(e) => {
                    setPasswordData((prev) => ({ ...prev, old_password: e.target.value }));
                    setPasswordError(null);
                  }}
                  className="input-neumorphic"
                  placeholder="••••••••"
                  required
                />
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>New Password</label>
                <input
                  type="password"
                  name="new_password"
                  value={passwordData.new_password}
                  onChange={(e) => {
                    setPasswordData((prev) => ({ ...prev, new_password: e.target.value }));
                    setPasswordError(null);
                  }}
                  className="input-neumorphic"
                  placeholder="••••••••"
                  required
                />
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Confirm New Password</label>
                <input
                  type="password"
                  name="confirm_password"
                  value={passwordData.confirm_password}
                  onChange={(e) => {
                    setPasswordData((prev) => ({ ...prev, confirm_password: e.target.value }));
                    setPasswordError(null);
                  }}
                  className="input-neumorphic"
                  placeholder="••••••••"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={passwordSaving}
              className="btn btn-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
            >
              {passwordSaving ? (
                <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <KeyRound size={18} />
              )}
              {passwordSaving ? 'Updating Password...' : 'Change Password'}
            </button>
          </form>
        </div>
      </Card>
    </div>

  );
};
