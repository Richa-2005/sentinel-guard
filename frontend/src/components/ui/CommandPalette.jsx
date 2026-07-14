import { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, Archive, ArrowRight, Home, Search, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

export default function CommandPalette() {
  const { commandOpen, setCommandOpen, transactions, setAuditSearch } = useApp();
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!commandOpen) return;
    setQuery('');
    requestAnimationFrame(() => inputRef.current?.focus());
    const onKey = (event) => event.key === 'Escape' && setCommandOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [commandOpen, setCommandOpen]);

  const commands = useMemo(() => {
    const base = [
      { label: 'Open live telemetry', hint: 'Workspace', icon: Activity, action: () => navigate('/app/live') },
      { label: 'Open incident command', hint: 'Workspace', icon: AlertTriangle, action: () => navigate('/app/incidents') },
      { label: 'Open compliance vault', hint: 'Workspace', icon: Archive, action: () => navigate('/app/vault') },
      { label: 'Return to landing page', hint: 'Navigation', icon: Home, action: () => navigate('/') },
    ];
    const matches = transactions.filter((item) => `${item.card_id} ${item.device_id}`.toLowerCase().includes(query.toLowerCase())).slice(0, 5).map((item) => ({
      label: item.card_id,
      hint: item.is_blocked ? 'Blocked transaction' : 'Transaction',
      icon: item.is_blocked ? AlertTriangle : Activity,
      action: () => {
        if (item.is_blocked) {
          setAuditSearch(item.card_id);
          navigate('/app/incidents', { state: { selectedKey: item._key } });
        } else navigate('/app/live');
      },
    }));
    return [...base, ...matches].filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(query.toLowerCase()));
  }, [navigate, query, transactions, setAuditSearch]);

  if (!commandOpen) return null;
  const run = (action) => { action(); setCommandOpen(false); };

  return (
    <div className="dialog-layer" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setCommandOpen(false)}>
      <section className="command-palette" role="dialog" aria-modal="true" aria-label="Command palette">
        <div className="command-input"><Search size={18} /><input ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search workspaces, cards, or devices" aria-label="Search commands" /><button className="icon-button" onClick={() => setCommandOpen(false)} aria-label="Close command palette"><X size={17} /></button></div>
        <div className="command-results" role="listbox">
          {commands.length ? commands.map((item, index) => <button key={`${item.label}-${index}`} onClick={() => run(item.action)} role="option"><item.icon size={16} /><span><strong>{item.label}</strong><small>{item.hint}</small></span><ArrowRight size={15} /></button>) : <p className="empty-inline">No matching actions or transaction identities.</p>}
        </div>
      </section>
    </div>
  );
}
