import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './components/Toast';
import Sidebar from './components/Sidebar';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import ProcessingPage from './pages/ProcessingPage';
import ValidationPage from './pages/ValidationPage';
import ReviewPage from './pages/ReviewPage';
import InsightsPage from './pages/InsightsPage';
import AdminPage from './pages/AdminPage';
import './App.css';

function AppShell() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  const isLogin = location.pathname === '/login';

  return (
    <div className="app__shell">
      {isAuthenticated && !isLogin && <Sidebar />}
      <main className={`app__main${!isAuthenticated || isLogin ? ' app__main--full' : ''}`}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/upload"    element={<ProtectedRoute><UploadPage /></ProtectedRoute>} />
          <Route path="/processing/:documentId" element={<ProtectedRoute><ProcessingPage /></ProtectedRoute>} />
          <Route path="/processing"             element={<ProtectedRoute><ProcessingPage /></ProtectedRoute>} />
          <Route path="/validation/:documentId" element={<ProtectedRoute><ValidationPage /></ProtectedRoute>} />
          <Route path="/validation"             element={<ProtectedRoute><ValidationPage /></ProtectedRoute>} />
          <Route path="/review/:documentId"     element={<ProtectedRoute><ReviewPage /></ProtectedRoute>} />
          <Route path="/review"                 element={<ProtectedRoute><ReviewPage /></ProtectedRoute>} />
          <Route path="/insights"               element={<ProtectedRoute><InsightsPage /></ProtectedRoute>} />
          <Route path="/admin"                  element={<ProtectedRoute allowedRoles={['admin']}><AdminPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <div className="app">
            <AppShell />
          </div>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
