import { AgentHistory, Evidence } from '@/domain/analysisResponse/types';
import axios from 'axios';
import { getAuthHeader } from './auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60 seconds for analysis
});

// Add auth token to requests if available
api.interceptors.request.use((config) => {
  const authHeader = getAuthHeader();
  if (authHeader) {
    config.headers.Authorization = authHeader;
  }
  return config;
});

// Handle errors including CORS
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle CORS errors
    if (!error.response && error.message?.includes('Network Error')) {
      console.error('CORS Error: Check that backend is running and CORS is configured');
      error.corsError = true;
      error.message = 'Cannot connect to backend. Check CORS configuration and ensure backend is running on ' + API_BASE_URL;
    }
    
    // Handle 401 errors (unauthorized) - clear auth
    if (error.response?.status === 401) {
      // Clear auth on unauthorized
      if (typeof window !== 'undefined') {
        localStorage.removeItem('incident_rag_auth_token');
        localStorage.removeItem('incident_rag_user');
        // Optionally redirect to login
        // window.location.href = '/login';
      }
    }
    
    return Promise.reject(error);
  }
);

export interface AnalysisRequest {
  query: string;
  timestamp: string;
  dashboard_images?: string[];
  log_files?: string[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  logs?: any[];
  services?: string[];
}

export interface TimeLine {
  // class TimelineEntry(BaseModel):
  //   time: str
  //   event: str
  //   source: str
  //   event_type: str

  time: string;
  event: string;
  source: string;
  event_type:string
}

export interface AnalysisResponse {
  analysis_id: string;
  status: 'answer' | 'refuse' | 'request_more_data';
  confidence: number;
  root_cause?: string;
  evidence?: Evidence;
  timeline?: TimeLine[];
  recommended_actions?: string[];
  alternative_hypotheses?: Array<{
    hypothesis: string;
    why_less_likely: string;
  }>;
  missing_evidence?: string[];
  processing_time_ms: number;
  agent_history: AgentHistory[];
}

export interface HealthResponse {
  status: string;
  version: string;
  agents_available: string[];
  mcp_enabled: boolean;
  mcp_servers: string[];
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await api.get('/health');
  return response.data;
}

export async function analyzeIncident(
  request: AnalysisRequest
): Promise<AnalysisResponse> {
  const response = await api.post('/analyze', request);
  return response.data;
}

export async function getAnalysis(analysisId: string): Promise<AnalysisResponse> {
  const response = await api.get(`/analysis/${analysisId}`);
  return response.data;
}

export async function createPlan(query: string, timestamp: string) {
  const formData = new FormData();
  formData.append('query', query);
  formData.append('timestamp', timestamp);
  
  const response = await api.post('/plan', formData);
  return response.data;
}

export async function getStats() {
  const response = await api.get('/stats');
  return response.data;
}

export async function listMcpServers() {
  const response = await api.get('/mcp/servers');
  return response.data;
}

// ---------------------------------------------------------------------------
// Settings (backend configuration)
// ---------------------------------------------------------------------------

export interface SettingSchema {
  key: string;
  type: string;
  default: string | number | boolean;
  label: string;
  description: string;
  secret: boolean;
  category: string;
}

export interface SettingsResponse {
  schema: SettingSchema[];
  values: Record<string, string | number | boolean>;
}

export async function getSettings(): Promise<SettingsResponse> {
  const response = await api.get('/settings');
  return response.data;
}

export async function updateSettings(values: Record<string, string | number | boolean>): Promise<SettingsResponse> {
  const response = await api.put('/settings', { values });
  return response.data;
}

// ---------------------------------------------------------------------------
// Authentication
// ---------------------------------------------------------------------------

export interface SignupRequest {
  email: string;
  password: string;
  name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  name?: string;
}

export interface UserProfile {
  id: string;
  email: string;
  name?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export async function signup(request: SignupRequest): Promise<AuthResponse> {
  const response = await api.post('/auth/signup', request);
  return response.data;
}

export async function login(request: LoginRequest): Promise<AuthResponse> {
  const response = await api.post('/auth/login', request);
  return response.data;
}

export async function getProfile(): Promise<UserProfile> {
  const response = await api.get('/auth/me');
  return response.data;
}

export async function updateProfile(name?: string): Promise<UserProfile> {
  const response = await api.put('/auth/me', { name });
  return response.data;
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

export interface AnalysisSummary {
  id: string;
  analysis_id: string;
  status: string;
  confidence: number;
  root_cause?: string;
  processing_time_ms: number;
  created_at: string;
}

export interface AnalysisListResponse {
  analyses: AnalysisSummary[];
  total: number;
  limit: number;
  offset: number;
}

export async function getAnalysisHistory(
  limit: number = 100,
  offset: number = 0,
  status?: string
): Promise<AnalysisListResponse> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  if (status) params.append('status', status);
  
  const response = await api.get(`/history?${params.toString()}`);
  return response.data;
}

export async function getAnalysisDetail(analysisId: string): Promise<AnalysisResponse> {
  const response = await api.get(`/history/${analysisId}`);
  return response.data;
}

export async function deleteAnalysis(analysisId: string): Promise<void> {
  await api.delete(`/history/${analysisId}`);
}

// ---------------------------------------------------------------------------
// Audit Logs
// ---------------------------------------------------------------------------

export interface AuditLogEntry {
  id: string;
  action: string;
  resource?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  details?: Record<string, any>;
  ip_address?: string;
  user_agent?: string;
  created_at: string;
}

export interface AuditLogListResponse {
  logs: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
}

export async function getAuditLogs(
  limit: number = 100,
  offset: number = 0,
  action?: string
): Promise<AuditLogListResponse> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  if (action) params.append('action', action);
  
  const response = await api.get(`/audit?${params.toString()}`);
  return response.data;
}

export default api;