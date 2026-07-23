import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import Notice from './Notice';
import { useApp } from '../../context/AppContext';
import DemoControl from './DemoControl';

export default function AppShell() {
  const { notice, setNotice, sidebarCollapsed } = useApp();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  useEffect(() => setMobileOpen(false), [location.pathname]);

  return (
    <div className="app-shell">
      <svg className="evidence-topology" viewBox="0 0 1600 900" aria-hidden="true">
        <defs><linearGradient id="topologyFlow" x1="0" x2="1"><stop stopColor="#b995ff"/><stop offset="1" stopColor="#ff765f"/></linearGradient></defs>
        <g className="topology-routes"><path d="M-20 145 C150 145 170 255 335 255 S555 125 720 125"/><path d="M910 95 C1090 95 1080 205 1245 205 S1450 90 1630 90"/><path d="M-30 765 C155 765 175 635 340 635 S545 780 730 780"/><path d="M895 815 C1070 815 1085 660 1245 660 S1460 790 1630 790"/><path d="M105 420 C190 350 275 350 360 420 S530 490 615 420"/></g>
        <g className="topology-nodes"><g transform="translate(82 145)"><circle r="8"/><text x="16" y="4">TRANSACTION</text></g><g transform="translate(335 255)"><circle r="8"/><text x="16" y="4">ENSEMBLE</text></g><g transform="translate(1245 205)"><circle r="8"/><text x="16" y="4">REVIEW</text></g><g transform="translate(340 635)"><circle r="8"/><text x="16" y="4">FINAL VERDICT</text></g><g transform="translate(1245 660)"><circle r="8"/><text x="16" y="4">AUDIT HASH</text></g></g>
        <circle className="topology-packet topology-packet--one" r="5"><animateMotion dur="8s" repeatCount="indefinite" path="M-20 145 C150 145 170 255 335 255 S555 125 720 125"/></circle><circle className="topology-packet topology-packet--two" r="5"><animateMotion dur="11s" repeatCount="indefinite" path="M895 815 C1070 815 1085 660 1245 660 S1460 790 1630 790"/></circle>
      </svg>
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <div className={`app-frame ${sidebarCollapsed ? 'app-frame--collapsed' : ''}`}>
        <TopBar onMenu={() => setMobileOpen(true)} />
        <main id="main-content" className="workspace" tabIndex="-1">
          <Outlet />
        </main>
      </div>
      <DemoControl />
      {notice && <Notice notice={notice} onClose={() => setNotice(null)} />}
    </div>
  );
}
