import React, { useState, useEffect, useRef } from 'react';
import { PageHeader } from '../../components/PageHeader';
import { Card } from '../../components/Card';
// unused imports removed
import { useAuth } from '../../contexts/AuthContext';
import { dataImportService } from '../../services/dataImport';
import type { CsvTemplate, ImportJob, ImportJobError } from '../../types/dataImport';
import { Upload, Download, Check, AlertCircle, FileText } from 'lucide-react';

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
    const currentIndex = ['select', 'upload', 'validate', 'preview', 'execute', 'result'].indexOf(step);
    
    return (
      <div className="flex items-center justify-between mb-8">
        {steps.map((s, idx) => {
          let stepIndex = idx;
          if (idx === 4) stepIndex = 5; // Result is index 5 in the array
          
          const isActive = currentIndex === stepIndex;
          const isPast = currentIndex > stepIndex;
          
          return (
            <div key={s} className="flex flex-col items-center flex-1">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                isActive ? 'bg-indigo-600 text-white' : 
                isPast ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'
              }`}>
                {isPast ? <Check /> : idx + 1}
              </div>
              <span className={`mt-2 text-xs font-medium ${isActive ? 'text-indigo-600' : 'text-gray-500'}`}>
                {s}
              </span>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <PageHeader
        title="Universal Data Import"
      />
      <p className="text-gray-600 mb-6 -mt-2">Import bulk data into HRMS securely and reliably.</p>

      {renderStepper()}

      {errorMessage && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-md flex items-start">
          <AlertCircle className="mt-0.5 mr-2 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {step === 'select' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {loading ? (
            <div className="col-span-3 text-center py-12 text-gray-500">Loading templates...</div>
          ) : (
            templates.map(t => (
              <div key={t.key} className="cursor-pointer h-full" onClick={() => handleTemplateSelect(t)}>
                <Card className="flex flex-col h-full hover:border-indigo-300 transition-colors">
                  <h3 className="text-lg font-medium text-gray-900 mb-2">{t.display_name}</h3>
                  <p className="text-sm text-gray-500 flex-grow">{t.description}</p>
                  <div className="mt-4 text-xs font-medium text-indigo-600 uppercase">
                    {t.headers.length} Columns
                  </div>
                </Card>
              </div>
            ))
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
              className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              <Download className="mr-2 -ml-1 h-4 w-4" />
              Download Template
            </button>
          </div>

          <div className="mt-6 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md">
            <div className="space-y-1 text-center">
              <Upload className="mx-auto h-12 w-12 text-gray-400" />
              <div className="flex text-sm text-gray-600 justify-center">
                <label
                  htmlFor="file-upload"
                  className="relative cursor-pointer bg-white rounded-md font-medium text-indigo-600 hover:text-indigo-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500"
                >
                  <span>Upload a file</span>
                  <input id="file-upload" name="file-upload" type="file" className="sr-only" accept=".csv" ref={fileInputRef} onChange={handleFileChange} />
                </label>
                <p className="pl-1">or drag and drop</p>
              </div>
              <p className="text-xs text-gray-500">CSV up to 10MB</p>
            </div>
          </div>

          {file && (
            <div className="mt-4 flex items-center justify-between p-3 bg-gray-50 rounded-md">
              <div className="flex items-center">
                <FileText className="text-gray-400 mr-2" />
                <span className="text-sm font-medium text-gray-900">{file.name}</span>
                <span className="ml-2 text-xs text-gray-500">({(file.size / 1024).toFixed(2)} KB)</span>
              </div>
              <button onClick={() => setFile(null)} className="text-sm text-red-600 hover:text-red-900">Remove</button>
            </div>
          )}

          <div className="mt-8 flex justify-end space-x-3">
            <button onClick={resetWorkflow} className="px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={!file || loading || !hasPermission('data_import.execute')}
              className={`px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white ${!file || loading || !hasPermission('data_import.execute') ? 'bg-indigo-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'}`}
            >
              {loading ? 'Uploading...' : 'Upload & Continue'}
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
            className={`px-6 py-3 border border-transparent shadow-sm text-base font-medium rounded-md text-white ${loading ? 'bg-indigo-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'}`}
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
          
          <div className="p-6 bg-gray-50 flex justify-end space-x-3">
            <button onClick={resetWorkflow} className="px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
              Cancel
            </button>
            <button
              onClick={handleExecute}
              disabled={loading}
              className={`px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white ${loading ? 'bg-indigo-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'}`}
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
                className="px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
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
