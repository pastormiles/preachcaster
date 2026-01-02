'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';

export default function DashboardPage() {
  const { user, church, isLoading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/auth/login');
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">PreachCaster</h1>
          <div className="flex items-center space-x-4">
            <span className="text-gray-600">{user.email}</span>
            <button
              onClick={logout}
              className="text-gray-500 hover:text-gray-700"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Church info card */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            {church?.name || 'Your Church'}
          </h2>
          <p className="text-gray-600 mb-4">
            Welcome to PreachCaster! Let&apos;s get your sermon podcast set up.
          </p>

          {/* Setup steps */}
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0 w-8 h-8 bg-green-100 text-green-600 rounded-full flex items-center justify-center">
                1
              </div>
              <div>
                <p className="font-medium text-gray-900">Account created</p>
                <p className="text-sm text-gray-500">Your church is registered</p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0 w-8 h-8 bg-gray-100 text-gray-400 rounded-full flex items-center justify-center">
                2
              </div>
              <div>
                <p className="font-medium text-gray-900">Connect YouTube</p>
                <p className="text-sm text-gray-500">Link your church&apos;s YouTube channel</p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0 w-8 h-8 bg-gray-100 text-gray-400 rounded-full flex items-center justify-center">
                3
              </div>
              <div>
                <p className="font-medium text-gray-900">Configure podcast</p>
                <p className="text-sm text-gray-500">Set up your podcast details</p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0 w-8 h-8 bg-gray-100 text-gray-400 rounded-full flex items-center justify-center">
                4
              </div>
              <div>
                <p className="font-medium text-gray-900">Publish</p>
                <p className="text-sm text-gray-500">Your sermons become a podcast</p>
              </div>
            </div>
          </div>
        </div>

        {/* Sermons section - placeholder */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Sermons</h2>
            <button
              disabled
              className="px-4 py-2 bg-indigo-600 text-white rounded-md opacity-50 cursor-not-allowed"
            >
              Connect YouTube First
            </button>
          </div>
          <p className="text-gray-500 text-center py-8">
            Connect your YouTube channel to start importing sermons
          </p>
        </div>
      </main>
    </div>
  );
}
