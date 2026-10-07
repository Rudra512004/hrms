import React, { useState, useEffect, useRef } from 'react';
import { PageHeader } from '../../components/PageHeader';
import { Card } from '../../components/Card';
// unused imports removed
import { useAuth } from '../../contexts/AuthContext';
import { dataImportService } from '../../services/dataImport';
import type { CsvTemplate, ImportJob, ImportJobError } from '../../types/dataImport';
import { Upload, Download, Check, AlertCircle, FileText, Users, MapPin, Building, Briefcase, CalendarDays, Umbrella, Clock, DollarSign, BatteryCharging } from 'lucide-react';

const TEMPLATE_META: Record<string, { icon: React.ElementType, color: string, bg: string }> = {
  'employees': { icon: Users, color: '#2563eb', bg: '#eff6ff' },
  'branches': { icon: MapPin, color: '#16a34a', bg: '#dcfce7' },
  'departments': { icon: Building, color: '#0284c7', bg: '#e0f2fe' },
  'designations': { icon: Briefcase, color: '#7c3aed', bg: '#f3e8ff' },
  'leave_types': { icon: Umbrella, color: '#db2777', bg: '#fce7f3' },
  'holidays': { icon: CalendarDays, color: '#ea580c', bg: '#ffedd5' },
  'attendance': { icon: Clock, color: '#d97706', bg: '#fef3c7' },
  'salary_structures': { icon: DollarSign, color: '#059669', bg: '#d1fae5' },
  'leave_balances': { icon: BatteryCharging, color: '#4f46e5', bg: '#e0e7ff' }
};

type ImportStep = 'select' | 'upload' | 'validate' | 'preview' | 'execute' | 'result';

export const DataImportPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const [templates, setTemplates] = useState<CsvTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<CsvTemplate | null>(null);
  const [step, setStep] = useState<ImportStep>('select');
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [errors, setErrors] = useState<ImportJobError[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      setLoading(true);
      const data = await dataImportService.getTemplates();
      setTemplates(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const handleTemplateSelect = (template: CsvTemplate) => {
    setSelectedTemplate(template);
    setStep('upload');
    setErrorMessage('');
  };

  const handleDownload = async () => {
    if (!selectedTemplate) return;
    try {
      await dataImportService.downloadTemplate(selectedTemplate.key, selectedTemplate.filename);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to download template');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setErrorMessage('');
    }
  };

  const handleUpload = async () => {
    if (!selectedTemplate || !file) return;
    try {
      setLoading(true);
      const newJob = await dataImportService.createJob(selectedTemplate.key, file);
      setJob(newJob);
      setStep('validate');
    } catch (err: any) {
      setErrorMessage(err.message || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    if (!job) return;
    try {
      setLoading(true);
      const updatedJob = await dataImportService.validateJob(job.id);
      setJob(updatedJob);
      setStep('preview');
    } catch (err: any) {
      setErrorMessage(err.message || 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!job) return;
    try {
      setLoading(true);
      const resultJob = await dataImportService.executeJob(job.id);
      setJob(resultJob);
      if (resultJob.error_count > 0) {
        const errorData = await dataImportService.getJobErrors(job.id);
        setErrors(errorData);
      }
      setStep('result');
    } catch (err: any) {
      setErrorMessage(err.message || 'Execution failed');
    } finally {
      setLoading(false);
    }
  };

  const resetWorkflow = () => {
    setStep('select');
    setSelectedTemplate(null);
    setFile(null);
    setJob(null);
    setErrors([]);
    setErrorMessage('');
  };

  if (!hasPermission('data_import.view')) {
    return <div className="p-6 text-center text-gray-500">You do not have permission to access Data Import.</div>;
  }

  const renderStepper = () => {
    const steps = ['Select Template', 'Upload', 'Validate', 'Preview', 'Result'];
    const currentStepIndex = ['select', 'upload', 'validate', 'preview', 'execute', 'result'].indexOf(step);
    // map execute to index 4 (Preview) during execution state, result to index 5
    const effectiveIndex = currentStepIndex === 4 ? 3 : currentStepIndex === 5 ? 4 : currentStepIndex;

    return (
      <div className="mb-10 w-full overflow-hidden">
        <div className="flex items-center justify-between relative w-full">
          {/* Background track */}
          <div className="absolute top-3 left-[10%] w-[80%] h-1 bg-gray-200 dark:bg-gray-700 rounded-full" />
          
          {/* Active track */}
          <div 
            className="absolute top-3 left-[10%] h-1 bg-indigo-600 rounded-full transition-all duration-300 ease-in-out" 
            style={{ width: `${(effectiveIndex / (steps.length - 1)) * 80}%` }}
          />

          {steps.map((s, idx) => {
            const isActive = effectiveIndex === idx;
            const isPast = effectiveIndex > idx;
            
            return (
              <div key={s} className="relative flex flex-col items-center z-10 w-1/5">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center border-2 transition-colors duration-300 ${
                  isPast 
                    ? 'bg-indigo-600 border-indigo-600' 
                    : isActive
                      ? 'bg-white dark:bg-gray-800 border-indigo-600'
                      : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600'
                }`}>
                  {isPast ? (
                    <Check className="w-4 h-4 text-white" strokeWidth={3} />
                  ) : isActive ? (
                    <div className="w-2.5 h-2.5 rounded-full bg-indigo-600" />
                  ) : null}
                </div>
                <span className={`mt-3 text-xs font-medium text-center transition-colors duration-300 ${
                  isActive ? 'text-indigo-600 dark:text-indigo-400' :
                  isPast ? 'text-gray-900 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'
                }`}>
                  {s}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <PageHeader 
        title="Universal Data Import" 
        subtitle="Import bulk data into HRMS securely and reliably."
      />
      {errorMessage && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-md flex items-start">
          <AlertCircle className="mt-0.5 mr-2 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
      
      {renderStepper()}

      {step === 'select' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-muted)' }}>Loading templates...</div>
          ) : (
            templates.map(t => {
              const meta = TEMPLATE_META[t.key] || { icon: FileText, color: '#475569', bg: '#f1f5f9' };
              const Icon = meta.icon;
              return (
              <div
                key={t.key}
                onClick={() => handleTemplateSelect(t)}
                style={{ cursor: 'pointer' }}
              >
                <Card className="flex flex-col">
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px', padding: '8px' }}>
                    <div style={{
                      width: 48,
                      height: 48,
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: meta.bg,
                      color: meta.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      <Icon size={24} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <h3 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 500, color: 'var(--color-text-main)', marginBottom: '8px' }}>{t.display_name}</h3>
                      <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-sub)' }}>{t.description}</p>
                      <div style={{ marginTop: '12px', fontSize: 'var(--font-size-xs)', fontWeight: 600, color: 'var(--color-primary)', textTransform: 'uppercase' }}>
                        {t.headers.length} Columns
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            )})
          )}
        </div>
      )}

      {step === 'upload' && selectedTemplate && (
        <Card className="max-w-2xl mx-auto">
          <div className="flex justify-between items-center mb-6 border-b pb-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-800">{selectedTemplate.display_name} Import</h2>
              <p className="text-sm text-gray-500 mt-1">Download the template and upload your populated CSV.</p>
            </div>
            <button
              onClick={handleDownload}
              className="btn btn-secondary"
            >
              <Download className="h-4 w-4" />
              Download Template
            </button>
          </div>

          <div className="mt-6 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md">
            <div className="space-y-1 text-center">
              <Upload className="mx-auto h-12 w-12 text-gray-400" />
              <div style={{ display: 'flex', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-sub)', justifyContent: 'center', gap: '4px' }}>
                <label
                  htmlFor="file-upload"
                  style={{ color: 'var(--color-primary)', cursor: 'pointer', fontWeight: 600 }}
                >
                  <span>Upload a file</span>
                  <input id="file-upload" name="file-upload" type="file" style={{ opacity: 0, position: 'absolute', zIndex: -1, width: '1px', height: '1px' }} accept=".csv" ref={fileInputRef} onChange={handleFileChange} />
                </label>
                <span>or drag and drop</span>
              </div>
              <p className="text-xs text-gray-500">CSV up to 10MB</p>
            </div>
          </div>

          {file && (
            <div className="mt-4 flex items-center justify-between p-3 bg-gray-50 rounded-md">
              <div className="flex items-center">
                <FileText className="text-gray-400 mr-2" />
                <span className="text-sm font-medium text-gray-900">{file.name}</span>
              </div>
              <button onClick={() => setFile(null)} className="btn btn-sm btn-ghost" style={{ color: 'var(--color-status-danger)' }}>Remove</button>
            </div>
          )}

          <div className="mt-8 flex justify-end gap-6">
            <button onClick={resetWorkflow} className="btn btn-secondary">
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={!file || loading || !hasPermission('data_import.execute')}
              className="btn btn-primary"
              title={
                !hasPermission('data_import.execute') 
                  ? "You don't have permission to execute imports" 
                  : !file 
                    ? "Please select a file above first" 
                    : ""
              }
            >
              {loading ? 'Uploading...' : !file ? 'Select a File to Continue' : 'Upload & Continue'}
            </button>
          </div>
        </Card>
      )}

      {step === 'validate' && job && (
        <Card className="max-w-2xl mx-auto text-center py-12">
          <h2 className="text-xl font-semibold text-gray-800 mb-2">File Uploaded Successfully</h2>
          <p className="text-sm text-gray-500 mb-8">We need to validate the structure and data types before executing the import.</p>
          
          <button
            onClick={handleValidate}
            disabled={loading}
            className="btn btn-primary btn-lg"
          >
            {loading ? 'Validating...' : 'Validate Import File'}
          </button>
        </Card>
      )}

      {step === 'preview' && job && (
        <Card className="overflow-hidden">
          <div className="p-6 border-b">
            <h2 className="text-xl font-semibold text-gray-800">Preview Data</h2>
            <p className="text-sm text-gray-500 mt-1">Review the first few rows to ensure the data is parsed correctly. Total Rows: {job.total_rows}</p>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Row</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Data Preview</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {job.preview_data.map((row, i) => (
                  <tr key={i}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{row.row}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {row.status === 'ok' ? (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">OK</span>
                      ) : (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">Error</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 font-mono">
                      {row.status === 'error' ? (
                        <span className="text-red-600">{row.error}</span>
                      ) : (
                        <div className="max-w-2xl truncate">
                          {JSON.stringify(row.data)}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <div className="p-6 bg-gray-50 flex justify-end gap-6">
            <button onClick={resetWorkflow} className="btn btn-secondary">
              Cancel
            </button>
            <button
              onClick={handleExecute}
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? 'Executing...' : 'Confirm & Execute Import'}
            </button>
          </div>
        </Card>
      )}

      {step === 'result' && job && (
        <div className="space-y-6">
          <Card className="text-center py-10">
            <div className={`mx-auto flex items-center justify-center h-16 w-16 rounded-full ${job.error_count > 0 ? 'bg-yellow-100' : 'bg-green-100'}`}>
              {job.error_count > 0 ? (
                <AlertCircle className="h-8 w-8 text-yellow-600" />
              ) : (
                <Check className="h-8 w-8 text-green-600" />
              )}
            </div>
            <h2 className="mt-4 text-2xl font-bold text-gray-900">
              {job.error_count > 0 ? 'Import Completed with Errors' : 'Import Successful'}
            </h2>
            <div className="mt-6 flex justify-center space-x-8">
              <div className="text-center">
                <p className="text-3xl font-semibold text-gray-900">{job.total_rows}</p>
                <p className="text-sm font-medium text-gray-500">Total Rows</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-semibold text-green-600">{job.created_count}</p>
                <p className="text-sm font-medium text-gray-500">Created</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-semibold text-blue-600">{job.updated_count}</p>
                <p className="text-sm font-medium text-gray-500">Updated</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-semibold text-gray-600">{job.skipped_count}</p>
                <p className="text-sm font-medium text-gray-500">Skipped</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-semibold text-red-600">{job.error_count}</p>
                <p className="text-sm font-medium text-gray-500">Errors</p>
              </div>
            </div>
            
            <div className="mt-10">
              <button
                onClick={resetWorkflow}
                className="btn btn-primary"
              >
                Start Another Import
              </button>
            </div>
          </Card>
          
          {errors.length > 0 && (
            <Card>
              <div className="p-6 border-b">
                <h3 className="text-lg font-medium text-gray-900">Error Report</h3>
                <p className="text-sm text-gray-500">The following rows failed to import.</p>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Row</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Field</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Error</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {errors.map((e, i) => (
                      <tr key={i}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{e.row_number}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-red-600">{e.field}</td>
                        <td className="px-6 py-4 text-sm text-gray-500">{e.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
};
