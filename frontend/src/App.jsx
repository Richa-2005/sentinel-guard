import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import AppShell from './components/ui/AppShell';
import PageSkeleton from './components/ui/PageSkeleton';

const LandingWelcome = lazy(() => import('./components/LandingWelcome'));
const RealTimeStream = lazy(() => import('./components/RealTimeStream'));
const IncidentCenter = lazy(() => import('./components/IncidentCenter'));
const ComplianceVault = lazy(() => import('./components/ComplianceVault'));

function LazyPage({ children }) {
  return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>;
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AppProvider>
        <Routes>
          <Route path="/" element={<LazyPage><LandingWelcome /></LazyPage>} />
          <Route path="/app" element={<AppShell />}>
            <Route index element={<Navigate to="live" replace />} />
            <Route path="live" element={<LazyPage><RealTimeStream /></LazyPage>} />
            <Route path="incidents" element={<LazyPage><IncidentCenter /></LazyPage>} />
            <Route path="vault" element={<LazyPage><ComplianceVault /></LazyPage>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppProvider>
    </BrowserRouter>
  );
}
