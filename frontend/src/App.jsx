import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import AppShell from './components/ui/AppShell';
import PageSkeleton from './components/ui/PageSkeleton';

const LandingWelcome = lazy(() => import('./components/LandingWelcome'));
const AuthPage = lazy(() => import('./components/AuthPage'));
const RealTimeStream = lazy(() => import('./components/RealTimeStream'));
const IncidentCenter = lazy(() => import('./components/IncidentCenter'));
const ComplianceVault = lazy(() => import('./components/ComplianceVault'));
const AdminOperations = lazy(() => import('./components/AdminOperations'));
const ModelHealth = lazy(() => import('./components/ModelHealth'));
const PeopleAccess = lazy(() => import('./components/PeopleAccess'));

function WorkspaceIndex() {
  const { user } = useAuth();
  return <Navigate to={user?.role === 'admin' ? 'operations' : 'reviews'} replace />;
}

function AdminRoute({ children }) {
  const { user } = useAuth();
  return user?.role === 'admin' ? children : <Navigate to="/app/reviews" replace />;
}

function LazyPage({ children }) {
  return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>;
}

function ProtectedWorkspace() {
  const { isAuthenticated, restoring } = useAuth();
  if (restoring) return <PageSkeleton />;
  if (!isAuthenticated) return <Navigate to="/signin" replace />;
  return <AppProvider><AppShell /></AppProvider>;
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LazyPage><LandingWelcome /></LazyPage>} />
          <Route path="/signin" element={<LazyPage><AuthPage /></LazyPage>} />
          <Route path="/app" element={<ProtectedWorkspace />}>
            <Route index element={<WorkspaceIndex />} />
            <Route path="transactions" element={<LazyPage><RealTimeStream /></LazyPage>} />
            <Route path="reviews" element={<LazyPage><IncidentCenter /></LazyPage>} />
            <Route path="vault" element={<LazyPage><ComplianceVault /></LazyPage>} />
            <Route path="operations" element={<AdminRoute><LazyPage><AdminOperations /></LazyPage></AdminRoute>} />
            <Route path="model-health" element={<AdminRoute><LazyPage><ModelHealth /></LazyPage></AdminRoute>} />
            <Route path="access" element={<AdminRoute><LazyPage><PeopleAccess /></LazyPage></AdminRoute>} />
            <Route path="live" element={<Navigate to="/app/transactions" replace />} />
            <Route path="incidents" element={<Navigate to="/app/reviews" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
