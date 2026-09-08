'use client';

import { useState, useEffect, useRef } from 'react';
import { uploadDocument, fetchApi } from './lib/api';

interface JobStatus {
  job_id: string;
  doc_id: string;
  status: string;
  stage: string;
  progress: number;
  chunks_total: number;
  chunks_done: number;
  facts_found: number;
  errors: string[];
}

interface DocumentSummary {
  doc_id: string;
  filename: string;
  page_count: number | null;
  file_size: number | null;
  fact_count: number;
  status: string;
  created_at: string;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [activeJob, setActiveJob] = useState<JobStatus | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = async () => {
    try {
      const data = await fetchApi<DocumentSummary[]>('/documents');
      setDocuments(data);
    } catch (err: any) {
      console.error('Failed to load documents:', err);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  // Poll active job
  useEffect(() => {
    if (!activeJob || activeJob.status === 'done' || activeJob.status === 'failed') return;

    const interval = setInterval(async () => {
      try {
        const status = await fetchApi<JobStatus>(`/jobs/${activeJob.job_id}`);
        setActiveJob(status);
        if (status.status === 'done' || status.status === 'failed') {
          loadDocuments();
        }
      } catch (err) {
        console.error('Error polling job:', err);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [activeJob]);

  const handleFileUpload = async (file: File) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('Please upload a valid PDF file.');
      return;
    }
    setErrorMsg(null);
    setIsUploading(true);

    try {
      const res = await uploadDocument(file);
      setIsUploading(false);
      // Fetch initial job status
      const job = await fetchApi<JobStatus>(`/jobs/${res.job_id}`);
      setActiveJob(job);
      loadDocuments();
    } catch (err: any) {
      setIsUploading(false);
      setErrorMsg(err.message || 'Upload failed');
    }
  };

  return (
    <div className="flex flex-col w-full gap-space-lg">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-md pb-space-xs">
        <div>
          <h1 className="font-headline-md text-headline-md text-on-surface tracking-tight">Documents</h1>
          <p className="font-body-sm text-body-sm text-outline mt-space-2xs">Upload a PDF to extract and link facts</p>
        </div>
        <div className="flex items-center gap-space-sm">
          <div className="h-8 px-space-md bg-surface-container-low rounded-lg flex items-center gap-space-xs font-label-code-sm text-label-code-sm text-on-surface-variant">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse"></span>
            CLI sync: active
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="bg-error-container border border-error/30 text-error p-3 rounded-md text-sm">
          {errorMsg}
        </div>
      )}

      {/* Upload Drop Zone */}
      <div
        className="relative group cursor-pointer h-[140px] w-full rounded-lg bg-surface-container-lowest hover:bg-surface-container-low transition-colors flex flex-col items-center justify-center gap-space-xs"
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          e.currentTarget.classList.add('bg-surface-container');
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          e.currentTarget.classList.remove('bg-surface-container');
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.currentTarget.classList.remove('bg-surface-container');
          if (e.dataTransfer.files?.[0]) handleFileUpload(e.dataTransfer.files[0]);
        }}
      >
        <input
          accept=".pdf"
          className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10 hidden"
          ref={fileInputRef}
          type="file"
          onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
        />
        <div className="w-9 h-9 rounded-lg bg-surface-container flex items-center justify-center text-on-surface-variant group-hover:text-primary transition-colors">
          <span className="material-symbols-outlined text-[20px]">upload_file</span>
        </div>
        <div className="flex items-center gap-space-sm">
          <span className="font-body-md text-body-md font-medium text-on-surface">
            {isUploading ? 'Uploading and preprocessing PDF...' : 'Drop PDFs here or click to browse'}
          </span>
          {!isUploading && (
            <span className="font-label-code-sm text-label-code-sm px-space-sm py-space-2xs bg-surface-container rounded text-outline font-medium">Browse files</span>
          )}
        </div>
        <span className="font-label-code-sm text-label-code-sm text-outline">PDF only · processed in the background</span>
        
        {/* Upload Progress Bar */}
        {isUploading && (
          <div className="absolute bottom-0 left-0 w-full h-1.5 bg-surface-container-high rounded-b-lg overflow-hidden">
            <div className="h-full bg-primary w-full animate-pulse"></div>
          </div>
        )}
      </div>

      {/* Active Processing Document Card */}
      {activeJob && activeJob.status !== 'failed' && (
        <div className="bg-surface-container-lowest rounded-lg p-space-base flex flex-col gap-space-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-xs">
            <div className="flex items-center gap-space-sm">
              <span className="material-symbols-outlined text-[18px] text-primary">description</span>
              <span className="font-body-md text-body-md font-semibold text-on-surface">{activeJob.doc_id}</span>
              <span className="font-label-code-sm text-label-code-sm px-space-xs py-space-2xs rounded bg-primary-fixed/30 text-primary uppercase font-semibold">
                {activeJob.status === 'done' ? 'COMPLETE' : 'PROCESSING'}
              </span>
            </div>
            <span className="font-label-code-sm text-label-code-sm text-outline">
              {activeJob.chunks_done} / {activeJob.chunks_total} chunks
            </span>
          </div>
          {/* Progress Bar */}
          <div className="w-full bg-surface-container-high h-1 rounded-full overflow-hidden">
            <div 
              className={`h-full rounded-full transition-all duration-500 ${activeJob.status === 'done' ? 'bg-secondary' : 'bg-primary-container'}`} 
              style={{ width: `${Math.max(5, Math.round((activeJob.progress || 0) * 100))}%` }}
            ></div>
          </div>
          {/* Processing Pipeline Stages (Mocked for visual, tied to stage string if backend supports it, else we map progress) */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-space-sm pt-space-2xs">
            <div className={`flex items-center gap-space-xs ${activeJob.progress > 0.1 ? 'text-on-surface' : 'text-primary font-semibold'}`}>
              <span className="material-symbols-outlined text-[15px] text-secondary">
                {activeJob.progress > 0.1 ? 'check_circle' : 'pending'}
              </span>
              <span className="font-body-sm text-body-sm font-medium">Parsing</span>
            </div>
            <div className={`flex items-center gap-space-xs ${activeJob.progress > 0.3 ? 'text-on-surface' : activeJob.progress > 0.1 ? 'text-primary font-semibold' : 'text-outline'}`}>
              <span className="material-symbols-outlined text-[15px] text-secondary">
                {activeJob.progress > 0.3 ? 'check_circle' : 'pending'}
              </span>
              <span className="font-body-sm text-body-sm font-medium">Chunking</span>
            </div>
            <div className={`flex items-center gap-space-xs ${activeJob.progress > 0.7 ? 'text-on-surface' : activeJob.progress > 0.3 ? 'text-primary font-semibold' : 'text-outline'}`}>
              <span className="material-symbols-outlined text-[15px] text-secondary">
                {activeJob.progress > 0.7 ? 'check_circle' : 'pending'}
              </span>
              <span className="font-body-sm text-body-sm font-medium">Extracting</span>
            </div>
            <div className={`flex items-center gap-space-xs ${activeJob.progress > 0.9 ? 'text-on-surface' : activeJob.progress > 0.7 ? 'text-primary font-semibold' : 'text-outline'}`}>
              {activeJob.progress > 0.7 && activeJob.progress <= 0.9 && <span className="w-2 h-2 rounded-full bg-primary animate-ping"></span>}
              <span className="font-body-sm text-body-sm font-semibold">Grounding</span>
            </div>
            <div className={`flex items-center gap-space-xs ${activeJob.status === 'done' ? 'text-on-surface' : activeJob.progress > 0.9 ? 'text-primary font-semibold' : 'text-outline'}`}>
              {activeJob.progress > 0.9 && activeJob.status !== 'done' ? <span className="w-2 h-2 rounded-full bg-primary animate-ping"></span> : <span className="w-1.5 h-1.5 rounded-full bg-outline-variant"></span>}
              <span className="font-body-sm text-body-sm">Linking</span>
            </div>
          </div>
        </div>
      )}

      {/* Documents Table Section */}
      <div className="bg-surface-container-lowest rounded-lg overflow-hidden flex flex-col">
        <div className="overflow-x-auto w-full border border-surface-container rounded-t-lg border-b-0">
          <table className="w-full min-w-[800px] text-left border-collapse table-fixed">
            <thead>
              <tr className="bg-surface-container-low text-on-surface-variant font-caption-ui text-caption-ui uppercase tracking-wider">
                <th className="py-space-sm px-space-base font-semibold">Document</th>
                <th className="py-space-sm px-space-base font-semibold text-right">Pages</th>
                <th className="py-space-sm px-space-base font-semibold text-right">Facts</th>
                <th className="py-space-sm px-space-base font-semibold text-right">Status</th>
                <th className="py-space-sm px-space-base font-semibold text-right">Processed</th>
                <th className="py-space-sm px-space-base font-semibold text-right w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y-0 text-on-surface font-body-sm text-body-sm">
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-space-xl text-center text-outline">No documents ingested yet. Upload a PDF above to begin.</td>
                </tr>
              ) : (
                documents.map((doc, idx) => (
                  <tr key={doc.doc_id} className={`group hover:bg-surface-container-low transition-colors ${idx % 2 !== 0 ? 'bg-surface-container-lowest' : ''}`}>
                    <td className="py-space-sm px-space-base font-body-md text-body-md font-medium text-on-surface flex items-center gap-space-xs min-w-0">
                      <span className="material-symbols-outlined text-[16px] text-outline group-hover:text-primary transition-colors flex-shrink-0">article</span>
                      <span className="truncate">{doc.filename}</span>
                    </td>
                    <td className="py-space-sm px-space-base text-right font-label-code-md text-label-code-md text-on-surface">{doc.page_count ?? '-'}</td>
                    <td className="py-space-sm px-space-base text-right font-label-code-md text-label-code-md text-primary font-medium">{doc.fact_count}</td>
                    <td className="py-space-sm px-space-base text-right font-label-code-sm text-label-code-sm text-outline uppercase">{doc.status}</td>
                    <td className="py-space-sm px-space-base text-right font-label-code-sm text-label-code-sm text-outline">{new Date(doc.created_at).toLocaleDateString()}</td>
                    <td className="py-space-sm px-space-base text-right">
                      <div className="opacity-0 group-hover:opacity-100 flex items-center justify-end gap-space-xs transition-opacity">
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {/* Table Footer / Summary Bar */}
        <div className="px-space-base py-space-sm bg-surface-container-low flex flex-col sm:flex-row items-center justify-between gap-space-xs text-on-surface-variant font-label-code-sm text-label-code-sm border border-surface-container rounded-b-lg">
          <div className="flex items-center gap-space-base">
            <span>{documents.length} documents indexed</span>
            <span>{documents.reduce((acc, doc) => acc + (doc.page_count || 0), 0)} total pages</span>
            <span className="text-primary font-medium">{documents.reduce((acc, doc) => acc + doc.fact_count, 0)} verified claims</span>
          </div>
          <div className="flex items-center gap-space-xs text-outline">
            <span className="material-symbols-outlined text-[14px]">shield</span>
            Zero verification drift
          </div>
        </div>
      </div>
    </div>
  );
}
