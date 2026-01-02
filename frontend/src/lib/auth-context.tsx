'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { authApi, User, Church, PodcastSettings } from './api';

interface AuthState {
  user: User | null;
  church: Church | null;
  podcastSettings: PodcastSettings | null;
  token: string | null;
  isLoading: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, churchName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    church: null,
    podcastSettings: null,
    token: null,
    isLoading: true,
  });
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      fetchUser(token);
    } else {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, []);

  const fetchUser = async (token: string) => {
    try {
      const data = await authApi.me(token);
      setState({
        user: data.user,
        church: data.church,
        podcastSettings: data.podcast_settings,
        token,
        isLoading: false,
      });
    } catch {
      localStorage.removeItem('token');
      setState({
        user: null,
        church: null,
        podcastSettings: null,
        token: null,
        isLoading: false,
      });
    }
  };

  const login = async (email: string, password: string) => {
    const response = await authApi.login({ email, password });
    localStorage.setItem('token', response.access_token);
    await fetchUser(response.access_token);
    router.push('/dashboard');
  };

  const register = async (email: string, password: string, churchName: string) => {
    const response = await authApi.register({ email, password, church_name: churchName });
    localStorage.setItem('token', response.access_token);
    await fetchUser(response.access_token);
    router.push('/dashboard');
  };

  const logout = () => {
    localStorage.removeItem('token');
    setState({
      user: null,
      church: null,
      podcastSettings: null,
      token: null,
      isLoading: false,
    });
    router.push('/');
  };

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
