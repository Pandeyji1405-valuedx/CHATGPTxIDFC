/**
 * Document and Ingestion TypeScript interfaces (Phase 3).
 *
 * Mirrors backend Pydantic models in app/schemas/document.py.
 */

export type DocumentStatus = 'ACTIVE' | 'INACTIVE' | 'SUPERSEDED';

export type IngestionStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  published_date: string | null;
  effective_date: string | null;
  status: DocumentStatus;
  file_name: string;
  file_hash: string;
  file_size_bytes: number;
  page_count: number;
  chunk_count: number;
  ingestion_status: IngestionStatus;
  error_message: string | null;
  superseded_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface RegulatoryDocument {
  id: string;
  document_key: string;
  title: string;
  document_type: string;
  circular_number: string | null;
  topic: string | null;
  source_name: string;
  source_url: string | null;
  created_at: string;
  updated_at: string;
  versions: DocumentVersion[];
}

export interface DocumentListResponse {
  items: RegulatoryDocument[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentUploadMetadata {
  title?: string;
  document_key?: string;
  document_type?: string;
  circular_number?: string;
  topic?: string;
  source_name?: string;
  source_url?: string;
  version_number?: number;
  published_date?: string;
  effective_date?: string;
  supersedes_version_id?: string;
}

export interface DocumentUploadResponse {
  document: RegulatoryDocument;
  version: DocumentVersion;
  message: string;
  chunks_indexed: number;
  is_duplicate: boolean;
}
