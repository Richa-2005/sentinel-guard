import { Activity, AlertTriangle, Archive, ChevronLeft, ChevronRight, HelpCircle, Landmark, X } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

const links = [
  { to: '/app/live', label: 'Live telemetry', icon: Activity },
  { to: '/app/incidents', label: 'Incident command', icon: AlertTriangle, count: true },
  { to: '/app/vault', label: 'Compliance vault', icon: Archive },
];

export default function Sidebar({ mobileOpen, onMobileClose }) {
  const { blockedTransactions, health, sidebarCollapsed, setSidebarCollapsed, setCommandOpen } = useApp();

  return (
    <>
      {mobileOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={onMobileClose} />}
      <aside className={`sidebar ${sidebarCollapsed ? 'sidebar--collapsed' : ''} ${mobileOpen ? 'sidebar--mobile-open' : ''}`} aria-label="Primary navigation">
        <div className="sidebar-brand">
          <div className="brand-mark" aria-hidden="true"><Landmark size={18} /></div>
          {!sidebarCollapsed && <div><strong>Sentinel Guard</strong><span>Risk operations</span></div>}
          <button className="icon-button sidebar-mobile-close" onClick={onMobileClose} aria-label="Close navigation"><X size={18} /></button>
        </div>

        <nav className="sidebar-nav">
          <span className="sidebar-label">Workspace</span>
          {links.map(({ to, label, icon: Icon, count }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`} title={sidebarCollapsed ? label : undefined}>
              <Icon size={17} aria-hidden="true" />
              {!sidebarCollapsed && <span>{label}</span>}
              {count && blockedTransactions.length > 0 && <span className="nav-count" aria-label={`${blockedTransactions.length} incidents`}>{blockedTransactions.length}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="nav-item" onClick={() => setCommandOpen(true)} title={sidebarCollapsed ? 'Help and commands' : undefined}>
            <HelpCircle size={17} /><span className={sidebarCollapsed ? 'sr-only' : ''}>Help & commands</span>
          </button>
          <div className="system-chip" title={`Risk core ${health}`}>
            <span className={`status-dot status-dot--${health}`} />
            {!sidebarCollapsed && <div><span>Risk core</span><strong>{health === 'online' ? 'Operational' : health === 'checking' ? 'Checking' : 'Unavailable'}</strong></div>}
          </div>
          <button className="collapse-control" onClick={() => setSidebarCollapsed((value) => !value)} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {sidebarCollapsed ? <ChevronRight size={16} /> : <><ChevronLeft size={16} /><span>Collapse</span></>}
          </button>
        </div>
      </aside>
    </>
  );
}
