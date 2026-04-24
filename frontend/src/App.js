import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './components/Toast';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import BatchUploadPage from './pages/BatchUploadPage';
import BatchStatusPage from './pages/BatchStatusPage';
import ProcessingPage from './pages/ProcessingPage';
import ValidationPage from './pages/ValidationPage';
import ReviewPage from './pages/ReviewPage';
import InsightsPage from './pages/InsightsPage';
import AdminPage from './pages/AdminPage';
import './App.css';

function AppRoutes() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <div className="app__content"><DashboardPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <div className="app__content"><UploadPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/batch-upload"
          element={
            <ProtectedRoute>
              <div className="app__content"><BatchUploadPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/batches/:batchId"
          element={
            <ProtectedRoute>
              <div className="app__content"><BatchStatusPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/processing/:documentId"
          element={
            <ProtectedRoute>
              <div className="app__content"><ProcessingPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/processing"
          element={
            <ProtectedRoute>
              <div className="app__content"><ProcessingPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/validation/:documentId"
          element={
            <ProtectedRoute>
              <div className="app__content"><ValidationPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/validation"
          element={
            <ProtectedRoute>
              <div className="app__content"><ValidationPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/review/:documentId"
          element={
            <ProtectedRoute>
              <div className="app__content"><ReviewPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/review"
          element={
            <ProtectedRoute>
              <div className="app__content"><ReviewPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/insights"
          element={
            <ProtectedRoute>
              <div className="app__content"><InsightsPage /></div>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <div className="app__content"><AdminPage /></div>
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <div className="app">
            <AppRoutes />
          </div>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
