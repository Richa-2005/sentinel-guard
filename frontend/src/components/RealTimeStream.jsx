import { useMemo, useState } from 'react';
import { ChevronDown, CircleStop, FileText, Play, Send, Upload } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { evaluateTransaction } from '../api/client';
import { useApp } from '../context/AppContext';
import useTrafficSimulator from '../hooks/useTrafficSimulator';
import { Badge, EmptyState, PageGuide } from './ui/Primitives';

const initial = { amount_paise: 27270, card_id: 'sql_card_02', device_id: 'sql_device_01', merchant_id: '7995' };
const presets = {
  baseline: { amount_paise: 1250, card_id: 'sql_card_01', device_id: 'dev_mac_001', merchant_id: '5411' },
  elevated: initial,
  hostile: { amount_paise: 450000, card_id: 'stolen_card_signature_02', device_id: 'malicious_device_ring_01', merchant_id: '4829' },
};
const money = (v = 0) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(v / 100);
const utc = (v) => v ? new Date(v).toLocaleString('en-GB', { timeZone: 'UTC', hour12: false }) + ' UTC' : '—';

export default function RealTimeStream() {
  const { transactions, liveStream, merchants, health, addTransaction, queueAudit, connectionStatus, setNotice, audits, auditStatuses, setSelectedAuditId, setAuditSearch } = useApp();
  const navigate = useNavigate();
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');
  const [decision, setDecision] = useState('all');
  const [form, setForm] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [reportMessage, setReportMessage] = useState('');

  const send = async (payload, { automated = false } = {}) => {
    setBusy(true); setError('');
    try {
      const transaction_id = payload.transaction_id || crypto.randomUUID();
      const result = await evaluateTransaction({ ...payload, transaction_id });
      const entry = addTransaction({ ...payload, ...result, transaction_id, timestamp: new Date().toISOString() });
      if (result.is_blocked) queueAudit(transaction_id);
      if (!automated) setNotice({ tone: result.is_blocked ? 'danger' : 'success', title: result.is_blocked ? 'Decision blocked' : 'Decision allowed', message: `${payload.card_id} was evaluated by the ensemble.` });
      return entry;
    } catch (e) { setError(e.message); return null; } finally { setBusy(false); }
  };
  const simulator = useTrafficSimulator(merchants, send, health === 'online');
  const rows = useMemo(() => {
    const map = new Map();
    [...transactions, ...liveStream].forEach((row) => map.set(row.transaction_id || row._key, { ...map.get(row.transaction_id || row._key), ...row }));
    return [...map.values()].filter((row) => {
      const hit = `${row.transaction_id} ${row.card_id} ${row.device_id} ${row.merchant_id}`.toLowerCase().includes(query.toLowerCase());
      return hit && (decision === 'all' || (decision === 'blocked') === Boolean(row.is_blocked));
    }).sort((a,b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));
  }, [transactions, liveStream, query, decision]);
  const blocked = rows.filter((r) => r.is_blocked).length;
  const selectedAudit = selected ? audits.find((record) => record.transaction_id === selected.transaction_id) : null;
  const selectedAuditStatus = selected ? auditStatuses[selected.transaction_id]?.status : null;

  const openReport = () => {
    if (selectedAudit) {
      setSelectedAuditId(selectedAudit.id);
      setAuditSearch(selected.transaction_id || selected.card_id || '');
      navigate('/app/vault');
      return;
    }
    setReportMessage(selectedAuditStatus === 'processing' || selectedAuditStatus === 'delayed'
      ? 'The report is still being prepared. Refresh the ledger shortly.'
      : selectedAuditStatus === 'failed'
        ? 'Report generation failed for this transaction. The decision remains available in the stream.'
        : 'No generated report exists for this transaction. Reports are created for blocked decisions.');
  };

  const replayCsv = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const parsed = String(reader.result).trim().split(/\r?\n/).slice(1).map((line) => line.split(','));
      for (const [amount, card, device, merchant] of parsed.slice(0, 50)) await send({ amount_paise: Number(amount), card_id: card, device_id: device, merchant_id: merchant }, { automated: true });
    };
    reader.readAsText(file);
  };

  return <div className="ops-page">
    <PageGuide title="Watch authenticated evaluations arrive through the live channel.">Search the decision ledger, inspect enriched signals, open a generated report, or use the controlled tools below to submit repeatable demonstration traffic.</PageGuide>
    <section className="ops-statusline"><div><span className={`status-dot status-dot--${connectionStatus === 'connected' ? 'online' : 'offline'}`} /><strong>{connectionStatus === 'connected' ? 'Live decision channel' : 'Decision channel reconnecting'}</strong></div><span>{rows.length} loaded</span><span>{blocked} blocked</span><span>{rows.length ? ((rows.length - blocked) / rows.length * 100).toFixed(1) : '100.0'}% allowed</span>{simulator.status !== 'stopped' && <Badge tone="warning">{simulator.status}</Badge>}</section>
    {error && <div className="ops-alert">{error}</div>}
    <section className="stream-console">
      <div className="stream-ledger">
        <div className="console-toolbar"><div><span className="eyebrow">Decision ledger</span><h2>Transaction stream</h2></div><label className="ops-search"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search ID, card, device or MCC" /></label><select value={decision} onChange={(e) => setDecision(e.target.value)}><option value="all">All decisions</option><option value="blocked">Blocked</option><option value="allowed">Allowed</option></select></div>
        <div className="ledger-head"><span>Time / transaction</span><span>Entity</span><span>Amount</span><span>Score</span><span>Decision</span></div>
        <div className="ledger-body">{rows.length ? rows.map((row) => <button key={row.transaction_id || row._key} className={`ledger-row ${selected === row ? 'is-selected' : ''}`} onClick={() => { setSelected(row); setReportMessage(''); }}><span><b>{new Date(row.timestamp || 0).toLocaleTimeString('en-GB', { timeZone:'UTC', hour12:false })}</b><small className="mono">{row.transaction_id || 'legacy'}</small></span><span><b className="mono">{row.card_id}</b><small className="mono">{row.device_id}</small></span><strong className="mono">{money(row.amount_paise)}</strong><strong className="mono">{(Number(row.ensemble_risk_score || 0) * 100).toFixed(3)}%</strong><Badge tone={row.is_blocked ? 'critical' : 'neutral'}>{row.is_blocked ? 'blocked' : 'allowed'}</Badge></button>) : <EmptyState title="No transactions match" message="Adjust the query or submit a controlled evaluation." />}</div>
      </div>
      <aside className="stream-inspector">
        <div className="inspector-heading"><span className="eyebrow">Decision inspector</span><h3>{selected ? selected.card_id : 'Select a row'}</h3></div>
        {selected ? <><div className="score-figure"><span>ensemble confidence</span><strong className="mono">{(Number(selected.ensemble_risk_score || 0)*100).toFixed(3)}%</strong><i style={{'--score': `${Number(selected.ensemble_risk_score || 0)*100}%`}} /></div><dl className="ops-dl"><div><dt>Transaction</dt><dd>{selected.transaction_id}</dd></div><div><dt>Device</dt><dd>{selected.device_id}</dd></div><div><dt>Merchant</dt><dd>{selected.merchant_id}</dd></div><div><dt>Evaluated</dt><dd>{utc(selected.timestamp)}</dd></div></dl><section className="inspector-signals"><div><span className="eyebrow">Enriched decision data</span><h4>Signals supplied to the ensemble</h4></div><dl>{Object.entries(selected.hydrated_metrics || {}).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd className="mono">{String(value)}</dd></div>)}</dl></section><button className="button button--primary inspector-report-button" onClick={openReport}><FileText size={15}/>{selectedAudit ? selectedAudit.is_error ? 'Open report error' : 'Open generated report' : 'Check generated report'}</button>{reportMessage && <p className="inspector-report-message" role="status">{reportMessage}</p>}</> : <p className="inspector-empty">The selected model decision, enriched signals, and exact UTC time appear here without leaving the stream.</p>}
      </aside>
    </section>
    <details className="evaluation-drawer"><summary><span><ChevronDown size={15}/><strong>Controlled evaluation tools</strong><small>Presets, manual payload, CSV replay and bounded simulator</small></span></summary><div className="evaluation-body"><div className="preset-line">{Object.entries(presets).map(([name,value]) => <button key={name} onClick={() => setForm(value)}>{name}</button>)}</div><form onSubmit={(e) => { e.preventDefault(); send({...form, amount_paise:Number(form.amount_paise)}); }}><label>Amount (paise)<input type="number" value={form.amount_paise} onChange={(e)=>setForm({...form,amount_paise:e.target.value})}/></label><label>Card ID<input value={form.card_id} onChange={(e)=>setForm({...form,card_id:e.target.value})}/></label><label>Device ID<input value={form.device_id} onChange={(e)=>setForm({...form,device_id:e.target.value})}/></label><label>Merchant<input value={form.merchant_id} onChange={(e)=>setForm({...form,merchant_id:e.target.value})}/></label><button className="button button--primary" disabled={busy}><Send size={14}/>Evaluate</button></form><div className="tool-actions"><button className="button button--secondary" onClick={simulator.status !== 'stopped' ? simulator.stop : simulator.start}>{simulator.status !== 'stopped' ? <CircleStop size={14}/> : <Play size={14}/>} {simulator.status !== 'stopped' ? 'Stop simulator' : 'Run simulator'}</button><label className="button button--secondary"><Upload size={14}/>Replay CSV<input hidden type="file" accept=".csv" onChange={(e)=>replayCsv(e.target.files?.[0])}/></label></div></div></details>
  </div>;
}
