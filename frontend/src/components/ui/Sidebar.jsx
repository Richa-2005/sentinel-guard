import { Activity, Archive, ChevronLeft, ChevronRight, Gauge, Landmark, ShieldAlert, Users, X } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';

const analystLinks = [
  { to: '/app/reviews', label: 'Work queue', icon: ShieldAlert, count: true },
  { to: '/app/transactions', label: 'Transaction stream', icon: Activity },
  { to: '/app/vault', label: 'Audit vault', icon: Archive },
];
const adminLinks = [
  { to: '/app/operations', label: 'Operations', icon: Gauge },
  { to: '/app/reviews', label: 'Review control', icon: ShieldAlert, count: true },
  { to: '/app/model-health', label: 'Model health', icon: Activity },
  { to: '/app/vault', label: 'Audit vault', icon: Archive },
  { to: '/app/access', label: 'People & access', icon: Users },
];

export default function Sidebar({ mobileOpen, onMobileClose }) {
  const { blockedTransactions, sidebarCollapsed, setSidebarCollapsed } = useApp();
  const { user } = useAuth();
  const links = user?.role === 'admin' ? adminLinks : analystLinks;

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
          <span className="sidebar-label">{user?.role === 'admin' ? 'Control plane' : 'Investigation desk'}</span>
          {links.map(({ to, label, icon: Icon, count }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`} title={sidebarCollapsed ? label : undefined}>
              <Icon size={17} aria-hidden="true" />
              {!sidebarCollapsed && <span>{label}</span>}
              {count && blockedTransactions.length > 0 && <span className="nav-count" aria-label={`${blockedTransactions.length} incidents`}>{blockedTransactions.length}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          {!sidebarCollapsed && <div className="sidebar-identity"><span>{user?.full_name}</span><small>{user?.role}</small></div>}
          <button className="collapse-control" onClick={() => setSidebarCollapsed((value) => !value)} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {sidebarCollapsed ? <ChevronRight size={16} /> : <><ChevronLeft size={16} /><span>Collapse</span></>}
          </button>
        </div>
      </aside>
    </>
  );
}
