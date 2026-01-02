const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ApiOptions {
  method?: string;
  body?: unknown;
  token?: string;
}

export async function api<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, token } = options;

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    method,
    headers,
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_URL}${endpoint}`, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
    throw new Error(error.detail || 'An error occurred');
  }

  return response.json();
}

// Auth API
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  church_name: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface Church {
  id: number;
  name: string;
  slug: string;
  youtube_channel_id: string | null;
  created_at: string;
}

export interface PodcastSettings {
  id: number;
  title: string;
  description: string | null;
  author: string | null;
  email: string | null;
  artwork_url: string | null;
  category: string;
  subcategory: string;
  language: string;
  website_url: string | null;
}

export interface MeResponse {
  user: User;
  church: Church | null;
  podcast_settings: PodcastSettings | null;
}

export const authApi = {
  login: (data: LoginRequest) =>
    api<TokenResponse>('/api/auth/login', { method: 'POST', body: data }),

  register: (data: RegisterRequest) =>
    api<TokenResponse>('/api/auth/register', { method: 'POST', body: data }),

  me: (token: string) =>
    api<MeResponse>('/api/auth/me', { token }),
};
