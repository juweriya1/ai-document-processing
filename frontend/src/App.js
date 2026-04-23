import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './hooks/useAuth';
import ProtectedRoute from './components/ProtectedRoute';
import AppLayout from './components/layout/AppLayout';

import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import ProcessingPage from './pages/ProcessingPage';
import ValidationPage from './pages/ValidationPage';
import ReviewPage from './pages/ReviewPage';
import InsightsPage from './pages/InsightsPage';
import SettingsPage from './pages/SettingsPage';
import NotFoundPage from './pages/NotFoundPage';

import './styles/globals.css';

function AuthenticatedLayout({ children }) {
  return (
    <ProtectedRoute>
      <AppLayout>{children}</AppLayout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="bottom-right"
          toastOptions={{ duration: 3500 }}
        />
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Authenticated */}
          <Route
            path="/dashboard"
            element={<AuthenticatedLayout><DashboardPage /></AuthenticatedLayout>}
          />
          <Route
            path="/upload"
            element={<AuthenticatedLayout><UploadPage /></AuthenticatedLayout>}
          />
          <Route
            path="/processing"
            element={<AuthenticatedLayout><ProcessingPage /></AuthenticatedLayout>}
          />
          <Route
            path="/validation"
            element={<AuthenticatedLayout><ValidationPage /></AuthenticatedLayout>}
          />
          <Route
            path="/review"
            element={<AuthenticatedLayout><ReviewPage /></AuthenticatedLayout>}
          />
          <Route
            path="/insights"
            element={<AuthenticatedLayout><InsightsPage /></AuthenticatedLayout>}
          />
          <Route
            path="/settings"
            element={<AuthenticatedLayout><SettingsPage /></AuthenticatedLayout>}
          />

          {/* Redirects */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
