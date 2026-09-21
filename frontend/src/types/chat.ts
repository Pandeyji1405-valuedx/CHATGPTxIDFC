/**
 * TypeScript interfaces for the Phase 4 Chat / RAG API.
 */

export interface Citation {
  document_id: string;
  version_id: string;
  document_title: string;
  circular_number: string | null;
  version_number: number;
  page_number: number;
  section: string | null;
  chunk_id: string;
}

export interface ChatMetrics {
  cache_hit?: boolean;
  cache_type?: string;
  tokens_saved?: number;
  total_latency_ms?: number;
  cache_lookup_latency_ms?: number;
  [key: string]: unknown;
}

export interface ChatMessage {
  id: string;
  role: 'USER' | 'ASSISTANT';
  content: string;
  retrieval_type?: string | null;
  citations?: Citation[] | null;
  metrics?: ChatMetrics | null;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface ChatRequest {
  conversation_id?: string | null;
  message: string;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  retrieval_type: string;
  citations: Citation[];
  created_at: string;
}
