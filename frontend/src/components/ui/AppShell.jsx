import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import CommandPalette from './CommandPalette';
import Notice from './Notice';
import { useApp } from '../../context/AppContext';

export default function AppShell() {
  const { notice, setNotice, sidebarCollapsed } = useApp();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  useEffect(() => setMobileOpen(false), [location.pathname]);

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <div className={`app-frame ${sidebarCollapsed ? 'app-frame--collapsed' : ''}`}>
        <TopBar onMenu={() => setMobileOpen(true)} />
        <main id="main-content" className="workspace" tabIndex="-1">
          <Outlet />
        </main>
      </div>
      <CommandPalette />
      {notice && <Notice notice={notice} onClose={() => setNotice(null)} />}
    </div>
  );
}
