import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Card } from '../../components/Card';
import { StatusBadge } from '../../components/StatusBadge';
import { Loader2, ArrowLeft, Mail, Phone, MapPin, Building, Briefcase, Calendar, User as UserIcon } from 'lucide-react';
import { EmptyState } from '../../components/EmptyState';

export const EmployeeProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [employee, setEmployee] = useState<EmployeeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'contact' | 'employment'>('overview');

  useEffect(() => {
    if (!id) return;
    const fetchProfile = async () => {
      setLoading(true);
      try {
        const data = await employeeManagementService.getEmployee(parseInt(id, 10));
        setEmployee(data);
        setError(null);
      } catch (err: any) {
        if (err.response?.status === 403) {
          setError("403 Forbidden: You do not have permission to view this profile.");
        } else if (err.response?.status === 404) {
          setError("404 Not Found: Employee does not exist.");
        } else {
          setError("Failed to load employee profile.");
        }
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [id]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
        <Loader2 className="animate-spin text-muted" size={40} />
      </div>
    );
  }

  if (error || !employee) {
    return (
      <div>
        <button className="btn btn-ghost" onClick={() => navigate('/admin/employees')} style={{ marginBottom: 'var(--spacing-md)' }}>
          <ArrowLeft size={16} /> Back to Directory
        </button>
        <Card>
          <EmptyState title="Error Loading Profile" description={error || "Profile not found."} icon={UserIcon} />
        </Card>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      {/* Top Action Bar */}
      <div>
        <button className="btn btn-ghost" onClick={() => navigate('/admin/employees')} style={{ padding: '4px 8px', marginLeft: '-8px' }}>
          <ArrowLeft size={16} /> Back to Directory
        </button>
      </div>

      {/* Header Card */}
      <Card style={{ padding: '0' }}>
        <div style={{ padding: 'var(--spacing-xl)', display: 'flex', alignItems: 'flex-start', gap: 'var(--spacing-xl)', flexWrap: 'wrap' }}>
          <div style={{ 
            width: '100px', height: '100px', borderRadius: 'var(--radius-lg)', 
            backgroundColor: 'var(--color-primary-light)', color: 'var(--color-primary)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '2rem', fontWeight: 600
          }}>
            {employee.first_name[0]}{employee.last_name[0]}
          </div>
          <div style={{ flex: 1, minWidth: '250px' }}>
            <h1 style={{ margin: '0 0 8px 0', fontSize: '1.75rem', fontWeight: 700 }}>
              {employee.first_name} {employee.last_name}
            </h1>
            <p style={{ margin: '0 0 12px 0', fontSize: '1rem', color: 'var(--color-text-muted)' }}>
              {employee.designation_name || 'No Designation'} &bull; {employee.department_name || 'No Department'}
            </p>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <StatusBadge status={(employee.employment_status || employee.status) as any} />
              <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Briefcase size={14} /> {employee.employee_code}
              </span>
            </div>
          </div>
        </div>
        
        {/* Tabs */}
        <div style={{ display: 'flex', borderTop: '1px solid var(--color-border)', padding: '0 var(--spacing-xl)' }}>
          {(['overview', 'contact', 'employment'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: activeTab === tab ? '2px solid var(--color-primary)' : '2px solid transparent',
                padding: '16px var(--spacing-md)',
                fontSize: '0.95rem',
                fontWeight: activeTab === tab ? 600 : 500,
                color: activeTab === tab ? 'var(--color-primary)' : 'var(--color-text-muted)',
                cursor: 'pointer',
                textTransform: 'capitalize'
              }}
            >
              {tab}
            </button>
          ))}
        </div>
      </Card>

      {/* Tab Content */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--spacing-lg)' }}>
        {activeTab === 'overview' && (
          <>
            <Card title="Identity Information">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Full Name</span>
                  <span style={{ fontWeight: 500 }}>{employee.first_name} {employee.last_name}</span>
                </div>
                <div>
                  <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Employee Code</span>
                  <span style={{ fontWeight: 500 }}>{employee.employee_code}</span>
                </div>
                <div>
                  <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>System Account Status</span>
                  <StatusBadge status={employee.status as any} />
                </div>
              </div>
            </Card>

            <Card title="Organizational Information">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <Building size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Department</span>
                    <span style={{ fontWeight: 500 }}>{employee.department_name || '-'}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <Briefcase size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Designation</span>
                    <span style={{ fontWeight: 500 }}>{employee.designation_name || '-'}</span>
                  </div>
                </div>
              </div>
            </Card>
          </>
        )}

        {activeTab === 'contact' && (
          <Card title="Contact Information" style={{ gridColumn: '1 / -1' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                <Mail size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                <div>
                  <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Work Email</span>
                  <span style={{ fontWeight: 500 }}>{employee.email}</span>
                </div>
              </div>

              {employee.personal_email !== undefined ? (
                <>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                    <Mail size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                    <div>
                      <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Personal Email</span>
                      <span style={{ fontWeight: 500 }}>{employee.personal_email || '-'}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                    <Phone size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                    <div>
                      <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Phone Number</span>
                      <span style={{ fontWeight: 500 }}>{employee.phone_number || '-'}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                    <MapPin size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                    <div>
                      <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Address</span>
                      <span style={{ fontWeight: 500 }}>{employee.address || '-'}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div style={{ gridColumn: '1 / -1', padding: '16px', backgroundColor: 'var(--color-bg-body)', borderRadius: 'var(--radius-md)' }}>
                  <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <UserIcon size={16} /> Sensitive contact information is restricted by your current role permissions.
                  </p>
                </div>
              )}
            </div>
            
            {employee.emergency_contact_name !== undefined && (
              <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid var(--color-border)' }}>
                <h3 style={{ fontSize: '1.05rem', margin: '0 0 16px 0' }}>Emergency Contact</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Name</span>
                    <span style={{ fontWeight: 500 }}>{employee.emergency_contact_name || '-'}</span>
                  </div>
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Phone</span>
                    <span style={{ fontWeight: 500 }}>{employee.emergency_contact_phone || '-'}</span>
                  </div>
                </div>
              </div>
            )}
          </Card>
        )}

        {activeTab === 'employment' && (
          <Card title="Employment Details" style={{ gridColumn: '1 / -1' }}>
             <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px' }}>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <Calendar size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Joining Date</span>
                    <span style={{ fontWeight: 500 }}>{employee.joining_date || '-'}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <Calendar size={18} color="var(--color-text-muted)" style={{ marginTop: '2px' }} />
                  <div>
                    <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Exit Date</span>
                    <span style={{ fontWeight: 500 }}>{employee.exit_date || '-'}</span>
                  </div>
                </div>
             </div>
          </Card>
        )}
      </div>
    </div>
  );
};
