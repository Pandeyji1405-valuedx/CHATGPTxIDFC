/**
 * Chat & RAG API service (Phase 4).
 *
 * Provides methods for sending regulatory questions and managing conversation history.
 */

import apiClient from './api';
import type {
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
} from '@/types/chat';

/**
 * Send a regulatory question and receive a grounded RAG answer.
 * Optionally continues an existing conversation (supply conversation_id).
 */
export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>('/api/v1/chat/message', request, {
    timeout: 120000, // 2 minutes — RAG pipeline can be slow on first run
  });
  return response.data;
}

/**
 * List all conversations belonging to the authenticated user.
 */
export async function listConversations(): Promise<ConversationSummary[]> {
  const response = await apiClient.get<ConversationSummary[]>('/api/v1/chat/conversations');
  return response.data;
}

/**
 * Retrieve a single conversation with its full message history.
 */
export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  const response = await apiClient.get<ConversationDetail>(
    `/api/v1/chat/conversations/${conversationId}`
  );
  return response.data;
}

/**
 * Delete a conversation and all its messages.
 */
export async function deleteConversation(conversationId: string): Promise<void> {
  await apiClient.delete(`/api/v1/chat/conversations/${conversationId}`);
}

/**
 * Submit user feedback for an assistant response message.
 */
export async function submitMessageFeedback(
  messageId: string,
  rating: 'POSITIVE' | 'NEGATIVE',
  reasonCategory?: string,
  comment?: string
): Promise<any> {
  const response = await apiClient.post(`/api/v1/chat/messages/${messageId}/feedback`, {
    rating,
    reason_category: reasonCategory,
    comment,
  });
  return response.data;
}

