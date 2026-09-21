import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '@/context/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { AppLayout } from '@/components/AppLayout';
import { LandingPage } from '@/pages/LandingPage';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import ChatPage from '@/pages/ChatPage';
import AdminDocumentsPage from '@/pages/AdminDocumentsPage';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected routes (wrapped in enterprise AppLayout shell) */}
          <Route element={<ProtectedRoute />}>
            <Route
              path="/chat"
              element={
                <AppLayout>
                  <ChatPage />
                </AppLayout>
              }
            />
          </Route>

          {/* ADMIN-only routes */}
          <Route element={<ProtectedRoute requiredRole="ADMIN" />}>
            <Route
              path="/admin/documents"
              element={
                <AppLayout>
                  <AdminDocumentsPage />
                </AppLayout>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
