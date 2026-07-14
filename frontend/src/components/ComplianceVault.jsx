import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Check, Clipboard, FileClock, FileText, Link2, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useApp } from '../context/AppContext';
import { Badge, EmptyState, Panel } from './ui/Primitives';

function enhancedReport(text = '') {
  return text
    .replace(/(REGULATORY COMPLIANCE CROSS-REFERENCE[^\n]*)/gi, '### $1')
    .replace(/(EXECUTIVE RISK VERDICT[^\n]*)/gi, '## $1')
    .replace(/(TECHNICAL SPECIFICATION PROFILE[^\n]*)/gi, '## $1')
    .replace(/(RBI[^\n]*)/gi, '**$1**')
    .replace(/(Visa[^\n]*)/gi, '**$1**');
}

function HashField({ label, value }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };
  return <div className="hash-field"><span>{label}</span><code>{value || 'Not recorded'}</code><button className="icon-button" onClick={copy} disabled={!value} aria-label={`Copy ${label}`}>{copied ? <Check size={15} /> : <Clipboard size={15} />}</button></div>;
}

export default function ComplianceVault() {
  const { audits, auditStatuses, loading, dataError, refreshAudits, auditSearch, setAuditSearch, selectedAuditId, setSelectedAuditId } = useApp();
  const [refreshing, setRefreshing] = useState(false);

  const filtered = useMemo(() => {
    const query = auditSearch.trim().toLowerCase();
    if (!query) return audits;
    return audits.filter((item) => `${item.card_id} ${item.report_text}`.toLowerCase().includes(query));
  }, [audits, auditSearch]);

  const selected = useMemo(() => audits.find((item) => item.id === selectedAuditId) || filtered[0] || null, [audits, filtered, selectedAuditId]);
  useEffect(() => { if (selected && selected.id !== selectedAuditId) setSelectedAuditId(selected.id); }, [selected, selectedAuditId, setSelectedAuditId]);

  const continuity = useMemo(() => {
    if (!selected?.previous_hash) return { matched: false, genesis: true, source: null };
    const previous = audits.find((item) => item.current_hash === selected.previous_hash);
    return { matched: Boolean(previous), genesis: /^0{64}$/.test(selected.previous_hash), source: previous };
  }, [audits, selected]);

  const refresh = async () => {
    setRefreshing(true);
    try { await refreshAudits(); } finally { setRefreshing(false); }
  };

  const pendingCount = Object.values(auditStatuses).filter((state) => state.status === 'processing' || state.status === 'delayed').length;

  return (
    <div className="page-stack">
      <section className="vault-summary"><div><span className="summary-icon summary-icon--success"><ShieldCheck size={20} /></span><div><strong>{audits.length} compliance records</strong><p>Chain-linked reports update automatically when background compilation completes.</p></div></div><div className="vault-actions">{pendingCount > 0 ? <Badge tone="warning">{pendingCount} processing</Badge> : <Badge tone="success">Live updates</Badge>}<button className="button button--secondary" onClick={refresh} disabled={refreshing}><RefreshCw size={15} className={refreshing ? 'spin' : ''} />Refresh records</button></div></section>

      {dataError && <div className="inline-alert" role="alert"><AlertTriangle size={17} /><div><strong>Vault synchronization issue</strong><p>{dataError}</p></div></div>}

      <div className="vault-layout">
        <Panel title="Record index" eyebrow="Audit ledger" className="vault-index" action={<span className="panel-count">{filtered.length}</span>}>
          <label className="search-field"><Search size={15} /><input value={auditSearch} onChange={(event) => { setAuditSearch(event.target.value); setSelectedAuditId(null); }} placeholder="Search card ID or report" aria-label="Search audit records" /></label>
          <div className="audit-list">
            {loading ? <div className="list-loading"><span className="skeleton" /><span className="skeleton" /><span className="skeleton" /></div> : !filtered.length ? <EmptyState title="No audit records found" message={auditSearch ? 'No records match the current search.' : 'Blocked transaction reports will appear here when compilation completes.'} /> : filtered.map((item) => <button key={item.id} className={`audit-item ${selected?.id === item.id ? 'audit-item--selected' : ''}`} onClick={() => setSelectedAuditId(item.id)}><span className={`record-icon ${item.is_error ? 'record-icon--error' : ''}`}>{item.is_error ? <FileClock size={16} /> : <FileText size={16} />}</span><span><strong className="mono">{item.card_id || 'Unknown card'}</strong><small className="mono">{item.timestamp || 'Historical record'}</small></span><Badge tone={item.is_error ? 'warning' : 'success'}>{item.is_error ? 'Generation issue' : 'Recorded'}</Badge></button>)}
          </div>
        </Panel>

        <Panel className="vault-document" aria-live="polite">
          {!selected ? <EmptyState title="Select a compliance record" message="Choose a record from the index to review its memorandum and chain metadata." /> : selected.is_error ? <div className="audit-error-state"><AlertTriangle size={26} /><span className="eyebrow">Report generation issue</span><h2>The risk decision is retained, but the memorandum was not completed.</h2><p>{selected.report_text}</p><button className="button button--secondary" onClick={refresh}>Check for newer records</button></div> : <article className="audit-document"><header><div><span className="eyebrow">Compliance memorandum</span><h2>Incident review record</h2></div><Badge tone="success">Chain-linked</Badge></header><div className="document-meta"><div><span>Target card</span><strong className="mono">{selected.card_id}</strong></div><div><span>Record time</span><strong className="mono">{selected.timestamp}</strong></div><div><span>Record ID</span><strong className="mono">#{selected.id}</strong></div></div><div className="markdown-report"><ReactMarkdown>{enhancedReport(selected.report_text)}</ReactMarkdown></div></article>}
        </Panel>

        <Panel title="Ledger continuity" eyebrow="Record metadata" className="vault-chain">
          {selected ? <div className="chain-content"><div className={`continuity-state ${continuity.matched || continuity.genesis ? 'continuity-state--matched' : 'continuity-state--unknown'}`}>{continuity.matched || continuity.genesis ? <Link2 size={19} /> : <AlertTriangle size={19} />}<div><strong>{continuity.genesis ? 'Genesis link recorded' : continuity.matched ? 'Continuity matched' : 'Predecessor not loaded'}</strong><p>{continuity.genesis ? 'This record begins the available chain.' : continuity.matched ? `Previous hash matches record #${continuity.source.id}.` : 'The referenced predecessor is outside the loaded record set or unavailable.'}</p></div></div><HashField label="Previous entry hash" value={selected.previous_hash} /><div className="chain-connector" aria-hidden="true"><span /><Link2 size={14} /><span /></div><HashField label="Current record hash" value={selected.current_hash} /><p className="chain-disclaimer">Continuity is determined by matching the recorded hash references supplied by the backend. This interface does not independently certify the source ledger.</p></div> : <EmptyState title="No chain metadata" message="Select an audit record to inspect its recorded hash references." />}
        </Panel>
      </div>
    </div>
  );
}
