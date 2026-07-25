import { LogOut, Menu, Play, RefreshCw } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';

const pageMeta = {
  '/app/transactions': ['Transaction stream', 'Inspect live model decisions and replay controlled traffic'],
  '/app/reviews': ['Human review', 'Resolve model escalations with attributable judgement'],
  '/app/vault': ['Audit vault', 'Read generated memoranda and verify ledger continuity'],
  '/app/operations': ['Operations', 'Decision throughput, review pressure, and system exceptions'],
  '/app/model-health': ['Model health', 'Distribution shift and human outcome monitoring'],
  '/app/access': ['People & access', 'Manage the two-role operating boundary'],
};

export default function TopBar({ onMenu }) {
  const { pathname } = useLocation();
  const { health, loading, hydrate, isDemoSession, demoStatus, setDemoControlOpen } = useApp();
  const { user, logout } = useAuth();
  const [title, subtitle] = pageMeta[pathname] || pageMeta['/app/reviews'];

  return (
    <header className="topbar">
      <div className="topbar-title">
        <button className="icon-button topbar-menu" onClick={onMenu} aria-label="Open navigation"><Menu size={18} /></button>
        <div><h1>{title}</h1><p>{subtitle}</p></div>
      </div>
      <div className="topbar-actions">
        {isDemoSession && <div className="live-demo-help">
          <button className={`live-demo-trigger ${demoStatus === 'running' ? 'is-running' : ''}`} onClick={() => setDemoControlOpen(true)} aria-describedby="live-demo-help">
            <Play size={14}/><span>{demoStatus === 'running' ? 'Demo running' : 'Run live demo'}</span>
          </button>
          <div className="live-demo-popover" id="live-demo-help" role="tooltip">
            <strong>Exercise the complete decision pipeline</strong>
            <span>Generate controlled safe and risky transactions, watch WebSocket updates, and follow blocked decisions into review and audit.</span>
          </div>
        </div>}
        <div className="health-label" aria-live="polite"><span className={`status-dot status-dot--${health}`} />{health === 'online' ? 'Systems operational' : health === 'checking' ? 'Checking systems' : 'Risk core unavailable'}</div>
        <button className="icon-button" onClick={hydrate} disabled={loading} aria-label="Refresh workspace data" title="Refresh workspace data">
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
        </button>
        <button className="icon-button" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={16} /></button>
      </div>
    </header>
  );
}
