import React, { useState } from 'react';
import {
  Network,
  Plus,
  Trash2,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  AlertCircle,
  Briefcase,
  Layers,
} from 'lucide-react';
import type { Stage3Payload, DepartmentItem, DesignationItem } from '../../../services/onboardingService';

interface Stage3StructureProps {
  initialData?: Partial<Stage3Payload>;
  isSubmitting: boolean;
  onBack: () => void;
  onSubmit: (data: Stage3Payload) => void;
  fieldErrors?: Record<string, string[]>;
}

const DEFAULT_DEPARTMENTS: DepartmentItem[] = [
  { name: 'Engineering', code: 'ENG', description: 'Software Development & Architecture' },
  { name: 'Human Resources', code: 'HR', description: 'People Operations & Talent Acquisition' },
  { name: 'Finance & Operations', code: 'FIN', description: 'Financial Accounting & General Operations' },
];

const DEFAULT_DESIGNATIONS: DesignationItem[] = [
  { name: 'Director / VP', code: 'DIR', level: 1 },
  { name: 'Engineering Lead', code: 'ENG-LEAD', level: 2 },
  { name: 'Senior Software Engineer', code: 'SR-SWE', level: 3 },
  { name: 'Software Engineer', code: 'SWE', level: 4 },
  { name: 'Associate Specialist', code: 'ASSOC', level: 5 },
];

export const Stage3Structure: React.FC<Stage3StructureProps> = ({
  initialData,
  isSubmitting,
  onBack,
  onSubmit,
  fieldErrors: _fieldErrors = {},
}) => {
  const [departments, setDepartments] = useState<DepartmentItem[]>(
    initialData?.departments && initialData.departments.length > 0
      ? initialData.departments
      : DEFAULT_DEPARTMENTS
  );

  const [designations, setDesignations] = useState<DesignationItem[]>(
    initialData?.designations && initialData.designations.length > 0
      ? initialData.designations
      : DEFAULT_DESIGNATIONS
  );

  const [validationError, setValidationError] = useState<string | null>(null);

  // Department handlers
  const handleAddDepartment = () => {
    setDepartments([...departments, { name: '', code: '', description: '' }]);
  };

  const handleUpdateDepartment = (index: number, field: keyof DepartmentItem, value: string) => {
    const updated = [...departments];
    updated[index] = { ...updated[index], [field]: value };
    setDepartments(updated);
  };

  const handleRemoveDepartment = (index: number) => {
    if (departments.length <= 1) {
      setValidationError('At least one department is required for operational readiness.');
      return;
    }
    setDepartments(departments.filter((_, i) => i !== index));
  };

  // Designation handlers
  const handleAddDesignation = () => {
    setDesignations([...designations, { name: '', code: '', level: designations.length + 1 }]);
  };

  const handleUpdateDesignation = (index: number, field: keyof DesignationItem, value: any) => {
    const updated = [...designations];
    updated[index] = { ...updated[index], [field]: value };
    setDesignations(updated);
  };

  const handleRemoveDesignation = (index: number) => {
    if (designations.length <= 1) {
      setValidationError('At least one designation is required for operational readiness.');
      return;
    }
    setDesignations(designations.filter((_, i) => i !== index));
  };

  const handleLoadPresets = () => {
    setDepartments(DEFAULT_DEPARTMENTS);
    setDesignations(DEFAULT_DESIGNATIONS);
    setValidationError(null);
  };

  const validate = (): boolean => {
    setValidationError(null);

    // Departments check
    if (departments.length === 0) {
      setValidationError('Please configure at least one department.');
      return false;
    }
    const deptNames = new Set<string>();
    for (const d of departments) {
      const cleanName = d.name.trim();
      if (!cleanName) {
        setValidationError('All departments must have a valid name.');
        return false;
      }
      if (deptNames.has(cleanName.toLowerCase())) {
        setValidationError(`Duplicate department name found: "${cleanName}".`);
        return false;
      }
      deptNames.add(cleanName.toLowerCase());
    }

    // Designations check
    if (designations.length === 0) {
      setValidationError('Please configure at least one designation.');
      return false;
    }
    const desigNames = new Set<string>();
    for (const d of designations) {
      const cleanName = d.name.trim();
      if (!cleanName) {
        setValidationError('All designations must have a valid name.');
        return false;
      }
      if (desigNames.has(cleanName.toLowerCase())) {
        setValidationError(`Duplicate designation name found: "${cleanName}".`);
        return false;
      }
      desigNames.add(cleanName.toLowerCase());
    }

    return true;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) {
      onSubmit({
        departments: departments.map((d) => ({
          name: d.name.trim(),
          code: d.code?.trim() || undefined,
          description: d.description?.trim() || undefined,
        })),
        designations: designations.map((d) => ({
          name: d.name.trim(),
          code: d.code?.trim() || undefined,
          level: d.level ? Number(d.level) : undefined,
        })),
      });
    }
  };

  return (
    <form noValidate onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Intro Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(168, 85, 247, 0.04) 100%)',
          border: '1px solid rgba(99, 102, 241, 0.2)',
          borderRadius: 'var(--radius-md, 8px)',
          padding: '16px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
          <Network size={24} style={{ color: 'var(--color-primary, #6366f1)', flexShrink: 0, marginTop: '2px' }} />
          <div>
            <h3 style={{ margin: '0 0 4px', fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-text-main, #0f172a)' }}>
              Organizational Hierarchy & Structure
            </h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--color-text-sub, #475569)', lineHeight: 1.5 }}>
              Configure operational departments (scoped to Head Office) and official employee designations.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleLoadPresets}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 12px',
            borderRadius: 'var(--radius-md, 8px)',
            background: 'var(--color-bg-card, #ffffff)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            color: 'var(--color-primary, #6366f1)',
            fontSize: '0.8125rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <Sparkles size={14} />
          Load Standard Defaults
        </button>
      </div>

      {validationError && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 'var(--radius-md, 8px)',
            background: 'var(--color-status-danger-bg, #fef2f2)',
            color: 'var(--color-status-danger, #ef4444)',
            border: '1px solid var(--color-status-danger-border, #fecaca)',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <AlertCircle size={16} />
          {validationError}
        </div>
      )}

      {/* Departments Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} style={{ color: 'var(--color-primary, #3b82f6)' }} />
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
              Departments ({departments.length})
            </h4>
          </div>

          <button
            type="button"
            onClick={handleAddDepartment}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--surface-control-bg, #f1f5f9)',
              border: '1px solid var(--color-border, #cbd5e1)',
              color: 'var(--color-text-main, #0f172a)',
              fontSize: '0.8125rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <Plus size={14} />
            Add Department
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {departments.map((dept, idx) => (
            <div
              key={`dept-${idx}`}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(180px, 1.2fr) minmax(100px, 0.8fr) minmax(200px, 1.8fr) 40px',
                gap: '10px',
                alignItems: 'center',
                padding: '10px 12px',
                borderRadius: 'var(--radius-md, 8px)',
                background: 'var(--surface-control-bg, #f8fafc)',
                border: '1px solid var(--color-border-subtle, #e2e8f0)',
              }}
            >
              <input
                type="text"
                required
                value={dept.name}
                onChange={(e) => handleUpdateDepartment(idx, 'name', e.target.value)}
                placeholder="Department Name (e.g. Engineering)"
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg-card, #ffffff)',
                  fontSize: '0.875rem',
                }}
              />
              <input
                type="text"
                value={dept.code || ''}
                onChange={(e) => handleUpdateDepartment(idx, 'code', e.target.value.toUpperCase())}
                placeholder="Code (ENG)"
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg-card, #ffffff)',
                  fontSize: '0.875rem',
                }}
              />
              <input
                type="text"
                value={dept.description || ''}
                onChange={(e) => handleUpdateDepartment(idx, 'description', e.target.value)}
                placeholder="Description"
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg-card, #ffffff)',
                  fontSize: '0.875rem',
                }}
              />
              <button
                type="button"
                onClick={() => handleRemoveDepartment(idx)}
                title="Remove department"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--color-status-danger, #ef4444)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Designations Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderTop: '1px solid var(--color-border-subtle, #f1f5f9)', paddingTop: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Briefcase size={18} style={{ color: 'var(--color-status-success, #10b981)' }} />
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-main, #0f172a)' }}>
              Designations ({designations.length})
            </h4>
          </div>

          <button
            type="button"
            onClick={handleAddDesignation}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              borderRadius: 'var(--radius-md, 8px)',
              background: 'var(--surface-control-bg, #f1f5f9)',
              border: '1px solid var(--color-border, #cbd5e1)',
              color: 'var(--color-text-main, #0f172a)',
              fontSize: '0.8125rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <Plus size={14} />
            Add Designation
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {designations.map((desig, idx) => (
            <div
              key={`desig-${idx}`}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(200px, 2fr) minmax(120px, 1fr) minmax(90px, 0.8fr) 40px',
                gap: '10px',
                alignItems: 'center',
                padding: '10px 12px',
                borderRadius: 'var(--radius-md, 8px)',
                background: 'var(--surface-control-bg, #f8fafc)',
                border: '1px solid var(--color-border-subtle, #e2e8f0)',
              }}
            >
              <input
                type="text"
                required
                value={desig.name}
                onChange={(e) => handleUpdateDesignation(idx, 'name', e.target.value)}
                placeholder="Designation Title (e.g. Software Engineer)"
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg-card, #ffffff)',
                  fontSize: '0.875rem',
                }}
              />
              <input
                type="text"
                value={desig.code || ''}
                onChange={(e) => handleUpdateDesignation(idx, 'code', e.target.value.toUpperCase())}
                placeholder="Code (SWE)"
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg-card, #ffffff)',
                  fontSize: '0.875rem',
                }}
              />
              <input
                type="number"
                min="1"
                max="20"
                value={desig.level ?? (idx + 1)}
                onChange={(e) => handleUpdateDesignation(idx, 'level', parseInt(e.target.value) || 1)}
                placeholder="Level (1-10)"
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg-card, #ffffff)',
                  fontSize: '0.875rem',
                }}
              />
              <button
                type="button"
                onClick={() => handleRemoveDesignation(idx)}
                title="Remove designation"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: 'var(--radius-sm, 6px)',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--color-status-danger, #ef4444)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Form Action Footer */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderTop: '1px solid var(--color-border, #e2e8f0)',
          paddingTop: '20px',
        }}
      >
        <button
          type="button"
          onClick={onBack}
          disabled={isSubmitting}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 20px',
            borderRadius: 'var(--radius-md, 8px)',
            background: 'var(--surface-control-bg, #f1f5f9)',
            color: 'var(--color-text-main, #0f172a)',
            border: '1px solid var(--color-border, #cbd5e1)',
            fontSize: '0.9375rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <ArrowLeft size={18} />
          Back to Head Office
        </button>

        <button
          type="submit"
          disabled={isSubmitting}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 24px',
            borderRadius: 'var(--radius-md, 8px)',
            background: 'var(--color-primary, #3b82f6)',
            color: '#ffffff',
            border: 'none',
            fontSize: '0.9375rem',
            fontWeight: 600,
            cursor: isSubmitting ? 'wait' : 'pointer',
            boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)',
          }}
        >
          {isSubmitting ? 'Saving Structure...' : 'Continue to Working Calendar'}
          <ArrowRight size={18} />
        </button>
      </div>
    </form>
  );
};
