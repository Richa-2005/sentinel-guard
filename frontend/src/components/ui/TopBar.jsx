import { Command, Menu, RefreshCw } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

const pageMeta = {
  '/app/live': ['Live telemetry', 'Evaluate and monitor transaction decisions'],
  '/app/incidents': ['Incident command', 'Triage blocked transactions and model signals'],
  '/app/vault': ['Compliance vault', 'Review chain-linked regulatory records'],
};

export default function TopBar({ onMenu }) {
  const { pathname } = useLocation();
  const { health, loading, hydrate, setCommandOpen } = useApp();
  const [title, subtitle] = pageMeta[pathname] || pageMeta['/app/live'];

  return (
    <header className="topbar">
      <div className="topbar-title">
        <button className="icon-button topbar-menu" onClick={onMenu} aria-label="Open navigation"><Menu size={18} /></button>
        <div><h1>{title}</h1><p>{subtitle}</p></div>
      </div>
      <div className="topbar-actions">
        <div className="health-label" aria-live="polite"><span className={`status-dot status-dot--${health}`} />{health === 'online' ? 'Systems operational' : health === 'checking' ? 'Checking systems' : 'Risk core unavailable'}</div>
        <button className="command-trigger" onClick={() => setCommandOpen(true)} aria-label="Open command palette">
          <Command size={15} /><span>Search</span><kbd>⌘ K</kbd>
        </button>
        <button className="icon-button" onClick={hydrate} disabled={loading} aria-label="Refresh workspace data">
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
        </button>
      </div>
    </header>
  );
}
