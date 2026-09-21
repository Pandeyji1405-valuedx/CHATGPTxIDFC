export type UserRole = 'USER' | 'ADMIN';

export interface HealthResponse {
  status: 'ok' | 'error';
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
}

export interface AuditLogEntry {
  id: string;
  tenant_id: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: string;
  correlation_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, any> | null;
  timestamp?: string;
  created_at?: string;
}

export interface AuditLogListResponse {
  total: number;
  items: AuditLogEntry[];
}

export interface ApiError {
  detail: string;
  status: 'error';
}

export type FetchStatus = 'idle' | 'loading' | 'success' | 'error';
