import { useEffect, useId, useMemo, useState } from 'react';
import {
  fetchDocumentById,
  fetchDocuments,
  uploadRbiDocument,
} from '@/services/documentService';
import type {
  DocumentListResponse,
  DocumentUploadResponse,
  RegulatoryDocument,
} from '@/types/document';

type IngestionPhase = 'idle' | 'uploading' | 'processing' | 'success' | 'error';

export default function AdminDocumentsPage() {
  const [docList, setDocList] = useState<DocumentListResponse | null>(null);
  const [isLoadingDocs, setIsLoadingDocs] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'catalog' | 'upload'>('catalog');

  const [filterTopic, setFilterTopic] = useState<string>('');
  const [filterType, setFilterType] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const [selectedDoc, setSelectedDoc] = useState<RegulatoryDocument | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const [title, setTitle] = useState<string>('');
  const [documentKey, setDocumentKey] = useState<string>('');
  const [documentType, setDocumentType] = useState<string>('circular');
  const [circularNumber, setCircularNumber] = useState<string>('');
  const [topic, setTopic] = useState<string>('');
  const [sourceName, setSourceName] = useState<string>('Reserve Bank of India');
  const [sourceUrl, setSourceUrl] = useState<string>('');
  const [versionNumber, setVersionNumber] = useState<string>('');
  const [publishedDate, setPublishedDate] = useState<string>('');
  const [effectiveDate, setEffectiveDate] = useState<string>('');
  const [supersedesVersionId, setSupersedesVersionId] = useState<string>('');

  const [uploadPhase, setUploadPhase] = useState<IngestionPhase>('idle');
  const [uploadResult, setUploadResult] = useState<DocumentUploadResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const fileInputId = useId();

  const loadDocuments = async () => {
    setIsLoadingDocs(true);
    setLoadError(null);
    try {
      const data = await fetchDocuments({
        topic: filterTopic || undefined,
        document_type: filterType || undefined,
        limit: 100,
      });
      setDocList(data);
    } catch (err: any) {
      setLoadError(err?.response?.data?.detail || 'Failed to load documents catalog.');
    } finally {
      setIsLoadingDocs(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [filterTopic, filterType]);

  // Determine if any document ingestion is actively in progress
  const isProcessing = useMemo(() => {
    if (uploadPhase === 'processing') return true;
    return Boolean(
      docList?.items?.some((item) =>
        item.versions?.some((v) => v.ingestion_status === 'PROCESSING')
      )
    );
  }, [uploadPhase, docList]);

  // Polling effect: poll every 3 seconds strictly while ingestion is in PROCESSING state
  useEffect(() => {
    if (!isProcessing) return;

    const intervalId = setInterval(async () => {
      try {
        const data = await fetchDocuments({
          topic: filterTopic || undefined,
          document_type: filterType || undefined,
          limit: 100,
        });
        setDocList(data);
      } catch (err) {
        // Silent catch during background polling
      }
    }, 3000);

    return () => {
      clearInterval(intervalId);
    };
  }, [isProcessing, filterTopic, filterType]);

  // Transition watcher: update upload banner state when background task finishes
  useEffect(() => {
    if (uploadResult && uploadPhase === 'processing' && docList?.items) {
      for (const doc of docList.items) {
        const ver = doc.versions?.find((v) => v.id === uploadResult.version.id);
        if (ver) {
          if (ver.ingestion_status === 'COMPLETED') {
            setUploadPhase('success');
            setUploadResult({
              ...uploadResult,
              version: ver,
              chunks_indexed: ver.chunk_count,
            });
          } else if (ver.ingestion_status === 'FAILED') {
            setUploadPhase('error');
            setUploadError(ver.error_message || 'Document ingestion failed.');
          }
        }
      }
    }
  }, [docList, uploadResult, uploadPhase]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setFileError('Only official .pdf files are accepted.');
      setSelectedFile(null);
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setFileError('File size exceeds maximum limit of 50 MB.');
      setSelectedFile(null);
      return;
    }

    setFileError(null);
    setSelectedFile(file);

    if (!title) {
      const cleanName = file.name
        .replace(/\.pdf$/i, '')
        .replace(/[_-]/g, ' ')
        .trim();
      setTitle(cleanName);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setFileError('Please choose an RBI PDF file to upload.');
      return;
    }

    setUploadPhase('uploading');
    setUploadError(null);
    setUploadResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    if (title.trim()) formData.append('title', title.trim());
    if (documentKey.trim()) formData.append('document_key', documentKey.trim());
    if (documentType.trim()) formData.append('document_type', documentType.trim());
    if (circularNumber.trim()) formData.append('circular_number', circularNumber.trim());
    if (topic.trim()) formData.append('topic', topic.trim());
    if (sourceName.trim()) formData.append('source_name', sourceName.trim());
    if (sourceUrl.trim()) formData.append('source_url', sourceUrl.trim());
    if (versionNumber.trim()) formData.append('version_number', versionNumber.trim());
    if (publishedDate.trim()) formData.append('published_date', publishedDate.trim());
    if (effectiveDate.trim()) formData.append('effective_date', effectiveDate.trim());
    if (supersedesVersionId.trim()) formData.append('supersedes_version_id', supersedesVersionId.trim());

    try {
      const res = await uploadRbiDocument(formData);
      if (res.version?.ingestion_status === 'PROCESSING') {
        setUploadPhase('processing');
      } else if (res.version?.ingestion_status === 'FAILED') {
        setUploadPhase('error');
        setUploadError(res.version.error_message || 'Document ingestion failed.');
      } else {
        setUploadPhase('success');
      }
      setUploadResult(res);
      loadDocuments();
    } catch (err: any) {
      setUploadPhase('error');
      let msg = 'Failed to ingest RBI document.';
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'string') {
        msg = detail;
      } else if (Array.isArray(detail)) {
        msg = detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
      } else if (detail) {
        msg = JSON.stringify(detail);
      } else if (err?.message) {
        msg = err.message;
      }
      setUploadError(msg);
    }
  };

  const handleViewDetail = async (docId: string) => {
    try {
      const detail = await fetchDocumentById(docId);
      setSelectedDoc(detail);
    } catch (err) {
      console.error(err);
    }
  };

  const filteredItems = useMemo(() => {
    if (!docList?.items) return [];
    return docList.items.filter((item) => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        item.title.toLowerCase().includes(q) ||
        item.document_key.toLowerCase().includes(q) ||
        (item.circular_number && item.circular_number.toLowerCase().includes(q))
      );
    });
  }, [docList, searchQuery]);

  // Aggregate Metrics
  const totalDocs = docList?.total ?? 0;
  const totalVersions = docList?.items.reduce((acc, d) => acc + (d.versions?.length || 1), 0) ?? 0;
  const totalChunks = docList?.items.reduce((acc, d) => acc + (d.versions?.[0]?.chunk_count || 0), 0) ?? 0;
  const totalPages = docList?.items.reduce((acc, d) => acc + (d.versions?.[0]?.page_count || 0), 0) ?? 0;

  return (
    <div className="flex-1 p-6 sm:p-8 bg-slate-950 text-slate-100 max-w-7xl mx-auto w-full space-y-8 animate-fade-in">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="badge-indigo text-[10px] font-mono uppercase">ADMIN WORKSPACE</span>
            <span className="text-slate-400 text-xs">• Governed Ingestion Engine</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold font-heading text-white tracking-tight">
            Knowledge Base Management
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Ingest, inspect, and manage approved RBI regulatory sources, version lifecycles, and ChromaDB vector indexing.
          </p>
        </div>

        <button
          onClick={loadDocuments}
          className="btn-secondary py-2 text-xs shrink-0 self-start sm:self-auto"
        >
          <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Refresh Data</span>
        </button>
      </div>

      {/* KPI METRIC CARDS ROW */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card-saas p-4 sm:p-5 flex items-center gap-4">
          <div className="w-11 h-11 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center justify-center text-xl shrink-0">
            📄
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Documents</p>
            <p className="text-xl sm:text-2xl font-extrabold font-heading text-white">{totalDocs}</p>
          </div>
        </div>

        <div className="card-saas p-4 sm:p-5 flex items-center gap-4">
          <div className="w-11 h-11 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center text-xl shrink-0">
            🌿
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Active Versions</p>
            <p className="text-xl sm:text-2xl font-extrabold font-heading text-white">{totalVersions}</p>
          </div>
        </div>

        <div className="card-saas p-4 sm:p-5 flex items-center gap-4">
          <div className="w-11 h-11 rounded-2xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 flex items-center justify-center text-xl shrink-0">
            ⚡
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Vector Chunks</p>
            <p className="text-xl sm:text-2xl font-extrabold font-heading text-white">{totalChunks}</p>
          </div>
        </div>

        <div className="card-saas p-4 sm:p-5 flex items-center gap-4">
          <div className="w-11 h-11 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center justify-center text-xl shrink-0">
            📚
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Ingested Pages</p>
            <p className="text-xl sm:text-2xl font-extrabold font-heading text-white">{totalPages}</p>
          </div>
        </div>
      </div>

      {/* PILL NAVIGATION TABS */}
      <div className="flex items-center gap-2 border-b border-slate-800">
        <button
          onClick={() => setActiveTab('catalog')}
          className={`px-4 py-2.5 text-xs font-bold font-heading border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'catalog'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          Regulatory Catalog ({filteredItems.length})
        </button>

        <button
          onClick={() => setActiveTab('upload')}
          className={`px-4 py-2.5 text-xs font-bold font-heading border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'upload'
              ? 'border-indigo-500 text-indigo-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Ingest RBI Circular (Upload)
        </button>
      </div>

      {/* TAB 1: REGULATORY CATALOG TABLE */}
      {activeTab === 'catalog' && (
        <div className="space-y-4 animate-fade-in">
          {/* Controls & Search Bar */}
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
            <div className="relative w-full sm:w-80">
              <input
                type="text"
                placeholder="Filter by title or circular #..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-saas py-2 text-xs pl-9"
              />
              <svg className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <select
                value={filterTopic}
                onChange={(e) => setFilterTopic(e.target.value)}
                className="input-saas py-2 text-xs w-full sm:w-44"
              >
                <option value="">All Topics</option>
                <option value="KYC & AML">KYC & AML</option>
                <option value="Prudential Norms">Prudential Norms</option>
                <option value="Digital Lending">Digital Lending</option>
              </select>

              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="input-saas py-2 text-xs w-full sm:w-40"
              >
                <option value="">All Types</option>
                <option value="circular">Circular</option>
                <option value="master_direction">Master Direction</option>
              </select>
            </div>
          </div>

          {/* Table Container */}
          <div className="card-saas overflow-hidden border border-slate-800">
            {isLoadingDocs ? (
              <div className="py-16 text-center text-slate-400 text-xs flex flex-col items-center justify-center gap-2">
                <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                Loading RBI regulatory catalog...
              </div>
            ) : loadError ? (
              <div className="p-4 bg-rose-500/10 text-rose-300 text-xs font-medium">{loadError}</div>
            ) : filteredItems.length === 0 ? (
              <div className="py-16 text-center text-slate-400 text-xs">
                No RBI documents match current search query.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                    <tr>
                      <th className="px-4 py-3">Document Title & Key</th>
                      <th className="px-4 py-3">Circular & Topic</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Latest Ver</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Chunks</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80 text-slate-200">
                    {filteredItems.map((doc) => {
                      const latestVer = doc.versions?.[0];
                      const verStatus = latestVer?.status || 'ACTIVE';
                      return (
                        <tr key={doc.id} className="hover:bg-slate-900/60 transition-colors">
                          <td className="px-4 py-3">
                            <div className="font-semibold text-white truncate max-w-xs">{doc.title}</div>
                            <div className="text-[10px] text-slate-400 font-mono truncate">{doc.document_key}</div>
                          </td>
                          <td className="px-4 py-3 text-slate-300">
                            <div>{doc.circular_number || '-'}</div>
                            <div className="text-[10px] text-indigo-400 font-semibold">{doc.topic || 'General'}</div>
                          </td>
                          <td className="px-4 py-3 text-slate-400 uppercase text-[10px] font-mono">{doc.document_type}</td>
                          <td className="px-4 py-3 text-indigo-400 font-bold font-mono">v{latestVer?.version_number || 1}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              verStatus === 'ACTIVE'
                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            }`}>
                              {verStatus}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-slate-300 font-mono text-[11px]">
                            {latestVer?.chunk_count ?? 0} chunks ({latestVer?.page_count ?? 0} pp)
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => handleViewDetail(doc.id)}
                              className="btn-secondary py-1 px-3 text-[11px]"
                            >
                              Inspect ({doc.versions?.length || 1})
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: INGEST RBI CIRCULAR (UPLOAD WIZARD) */}
      {activeTab === 'upload' && (
        <form onSubmit={handleUploadSubmit} className="space-y-6 max-w-4xl mx-auto animate-fade-in">
          <div className="card-saas p-6 sm:p-8 space-y-6">
            <h2 className="text-lg font-bold font-heading text-white flex items-center gap-2 border-b border-slate-800 pb-3">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 shadow-glow"></span>
              Upload & Ingest RBI Regulatory PDF Document
            </h2>

            {/* File Drag Drop Zone */}
            <div>
              <label htmlFor={fileInputId} className="label-saas">
                Upload Official RBI PDF Document *
              </label>
              <div className="border-2 border-dashed border-slate-800 hover:border-indigo-500/50 bg-slate-950/50 rounded-2xl p-8 text-center transition-all cursor-pointer">
                <input
                  id={fileInputId}
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <label htmlFor={fileInputId} className="cursor-pointer space-y-3 block">
                  <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center justify-center text-2xl mx-auto">
                    📥
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {selectedFile ? selectedFile.name : 'Click to choose or drag & drop RBI PDF circular'}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      {selectedFile
                        ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready for ingestion`
                        : 'Supported format: Official RBI PDF up to 50 MB'}
                    </p>
                  </div>
                </label>
              </div>
              {fileError && <p className="text-xs text-rose-400 mt-2">{fileError}</p>}
            </div>

            {/* Document Metadata Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label-saas">Document Title *</label>
                <input
                  type="text"
                  placeholder="Master Direction - KYC Direction, 2016"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="input-saas"
                  required
                />
              </div>

              <div>
                <label className="label-saas">Document Key / Identifier</label>
                <input
                  type="text"
                  placeholder="rbi-kyc-master-direction"
                  value={documentKey}
                  onChange={(e) => setDocumentKey(e.target.value)}
                  className="input-saas font-mono text-xs"
                />
              </div>

              <div>
                <label className="label-saas">Document Type</label>
                <select
                  value={documentType}
                  onChange={(e) => setDocumentType(e.target.value)}
                  className="input-saas"
                >
                  <option value="circular">Circular</option>
                  <option value="master_direction">Master Direction</option>
                  <option value="guideline">Guideline</option>
                  <option value="notification">Notification</option>
                </select>
              </div>

              <div>
                <label className="label-saas">Circular Number</label>
                <input
                  type="text"
                  placeholder="RBI/2015-16/18"
                  value={circularNumber}
                  onChange={(e) => setCircularNumber(e.target.value)}
                  className="input-saas font-mono text-xs"
                />
              </div>

              <div>
                <label className="label-saas">Topic / Category</label>
                <input
                  type="text"
                  placeholder="KYC & AML"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="input-saas"
                />
              </div>

              <div>
                <label className="label-saas">Published Date</label>
                <input
                  type="date"
                  value={publishedDate}
                  onChange={(e) => setPublishedDate(e.target.value)}
                  className="input-saas"
                />
              </div>

              <div>
                <label className="label-saas">Source Name</label>
                <input
                  type="text"
                  placeholder="Reserve Bank of India"
                  value={sourceName}
                  onChange={(e) => setSourceName(e.target.value)}
                  className="input-saas"
                />
              </div>

              <div>
                <label className="label-saas">Source URL</label>
                <input
                  type="text"
                  placeholder="https://www.rbi.org.in/..."
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  className="input-saas text-xs"
                />
              </div>

              <div>
                <label className="label-saas">Version Number</label>
                <input
                  type="text"
                  placeholder="e.g. 1"
                  value={versionNumber}
                  onChange={(e) => setVersionNumber(e.target.value)}
                  className="input-saas"
                />
              </div>

              <div>
                <label className="label-saas">Effective Date</label>
                <input
                  type="date"
                  value={effectiveDate}
                  onChange={(e) => setEffectiveDate(e.target.value)}
                  className="input-saas"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="label-saas">Supersedes Version ID (Optional)</label>
                <input
                  type="text"
                  placeholder="UUID of older version to supersede and invalidate in cache"
                  value={supersedesVersionId}
                  onChange={(e) => setSupersedesVersionId(e.target.value)}
                  className="input-saas font-mono text-xs"
                />
              </div>
            </div>

            {/* Upload Status / Progress Feedback */}
            {uploadPhase === 'uploading' && (
              <div className="p-4 bg-indigo-500/10 border border-indigo-500/30 rounded-xl text-xs text-indigo-300 flex items-center gap-3">
                <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin"></div>
                <span>Ingesting PDF via PyMuPDF, generating Nomic embeddings, and indexing into ChromaDB...</span>
              </div>
            )}

            {uploadPhase === 'success' && uploadResult && (
              <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs text-emerald-300 space-y-1">
                <p className="font-bold">✓ Document Ingestion & Vector Indexing Complete!</p>
                <p>Chunks Indexed: {uploadResult.chunks_indexed} | Pages Extracted: {uploadResult.version.page_count}</p>
              </div>
            )}

            {uploadPhase === 'error' && uploadError && (
              <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300">
                {uploadError}
              </div>
            )}

            {/* Submit Action */}
            <button
              type="submit"
              disabled={uploadPhase === 'uploading'}
              className="btn-primary w-full py-3 text-sm font-semibold shadow-glow"
            >
              Ingest & Index RBI Document
            </button>
          </div>
        </form>
      )}

      {/* INSPECT DOCUMENT DRAWER MODAL */}
      {selectedDoc && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full p-6 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="font-bold text-white font-heading text-lg">{selectedDoc.title}</h3>
                <p className="text-xs text-slate-400 font-mono">{selectedDoc.document_key}</p>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="p-1.5 text-slate-400 hover:text-white rounded-xl bg-slate-800"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs text-slate-300">
              <div className="grid grid-cols-2 gap-3 bg-slate-950 p-4 rounded-xl border border-slate-800">
                <div><strong className="text-white">Circular #:</strong> {selectedDoc.circular_number || '-'}</div>
                <div><strong className="text-white">Topic:</strong> {selectedDoc.topic}</div>
                <div><strong className="text-white">Source:</strong> {selectedDoc.source_name}</div>
                <div><strong className="text-white">Total Versions:</strong> {selectedDoc.versions?.length || 1}</div>
              </div>

              <h4 className="font-bold text-white text-xs uppercase tracking-wider">Version History</h4>
              <div className="space-y-2">
                {selectedDoc.versions?.map((v) => (
                  <div key={v.id} className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between">
                    <div>
                      <span className="font-bold text-indigo-400 font-mono">v{v.version_number}</span>
                      <span className="text-slate-400 ml-2">({v.page_count} pages • {v.chunk_count} chunks)</span>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      v.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                    }`}>
                      {v.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end pt-4 border-t border-slate-800">
              <button onClick={() => setSelectedDoc(null)} className="btn-secondary text-xs">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
