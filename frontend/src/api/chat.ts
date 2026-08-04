import apiClient from './client';

export interface ChatSession {
  id: string;
  project_id: string | null;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: string;
  content: string;
  model_name: string | null;
  tokens_used: number | null;
  meta_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export async function listProjectChatSessions(projectId: string) {
  const res = await apiClient.get(`/api/projects/${projectId}/chat-sessions`);
  return res.data as ChatSession[];
}

export async function createChatSession(projectId?: string, title?: string) {
  const res = await apiClient.post("/api/chat-sessions", {
    project_id: projectId || null,
    title: title || undefined,
  });
  return res.data as ChatSession;
}

export async function getChatSession(sessionId: string) {
  const res = await apiClient.get(`/api/chat-sessions/${sessionId}`);
  return res.data as ChatSessionDetail;
}

export async function sendChatMessage(sessionId: string, content: string) {
  const res = await apiClient.post(`/api/chat-sessions/${sessionId}/messages`, {
    content,
  });
  return res.data as ChatMessage;
}

export async function deleteChatSession(sessionId: string) {
  await apiClient.delete(`/api/chat-sessions/${sessionId}`);
}
