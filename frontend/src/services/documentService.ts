/**
 * Document & Knowledge Base API service (Phase 3).
 *
 * Handles official RBI PDF uploads, document catalog retrieval,
 * and version inspection via the central axios client.
 */

import apiClient from './api';
import type {
  DocumentListResponse,
  DocumentUploadResponse,
  DocumentVersion,
  RegulatoryDocument,
} from '@/types/document';

export interface DocumentQueryParams {
  limit?: number;
  offset?: number;
  topic?: string;
  document_type?: string;
}

/**
 * Upload and ingest an official RBI regulatory PDF (ADMIN only).
 *
 * Sends a multipart/form-data POST request to /api/v1/documents/upload.
 */
export async function uploadRbiDocument(formData: FormData): Promise<DocumentUploadResponse> {
  const response = await apiClient.post<DocumentUploadResponse>(
    '/api/v1/documents/upload',
    formData,
    {
      headers: {
        'Content-Type': undefined,
      },
      // Give sufficient timeout for extraction, embedding, and ChromaDB indexing (3 minutes)
      timeout: 180_000,
    },
  );
  return response.data;
}

/**
 * Fetch paginated list of RBI regulatory documents with version history.
 */
export async function fetchDocuments(params?: DocumentQueryParams): Promise<DocumentListResponse> {
  const response = await apiClient.get<DocumentListResponse>('/api/v1/documents', {
    params: {
      limit: params?.limit ?? 50,
      offset: params?.offset ?? 0,
      topic: params?.topic || undefined,
      document_type: params?.document_type || undefined,
    },
  });
  return response.data;
}

/**
 * Fetch details and complete version history for a single document.
 */
export async function fetchDocumentById(documentId: string): Promise<RegulatoryDocument> {
  const response = await apiClient.get<RegulatoryDocument>(`/api/v1/documents/${documentId}`);
  return response.data;
}

/**
 * Fetch list of versions for a given document UUID.
 */
export async function fetchDocumentVersions(documentId: string): Promise<DocumentVersion[]> {
  const response = await apiClient.get<DocumentVersion[]>(`/api/v1/documents/${documentId}/versions`);
  return response.data;
}

/**
 * Fetch specific version details and indexing metrics.
 */
export async function fetchVersionDetail(
  documentId: string,
  versionId: string,
): Promise<DocumentVersion> {
  const response = await apiClient.get<DocumentVersion>(
    `/api/v1/documents/${documentId}/versions/${versionId}`,
  );
  return response.data;
}
