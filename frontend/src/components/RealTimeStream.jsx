import { useCallback, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { AlertTriangle, ArrowDownUp, CheckCircle2, ChevronRight, CircleStop, CloudUpload, Play, Send, X } from 'lucide-react';
import { evaluateTransaction } from '../api/client';
import { useApp } from '../context/AppContext';
import useTrafficSimulator from '../hooks/useTrafficSimulator';
import { Badge, EmptyState, Metric, Panel } from './ui/Primitives';

const defaultForm = { amount_paise: 27270, card_id: 'sql_card_02', device_id: 'sql_device_01', merchant_id: '7995' };
const presets = {
  standard: { amount_paise: 1250, card_id: 'sql_card_01', device_id: 'dev_mac_001', merchant_id: '5411' },
  elevated: { amount_paise: 27370, card_id: 'card_token_999', device_id: 'malicious_device_ring_01', merchant_id: '7995' },
  ceiling: { amount_paise: 450000, card_id: 'stolen_card_signature_02', device_id: 'malicious_device_ring_01', merchant_id: '4829' },
};

const formatCurrency = (value = 0) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value / 100);
const formatTime = (value) => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';

export default function RealTimeStream() {
  const { transactions, merchants, stats, health, dataError, addTransaction, audits, pollForAudit, setNotice } = useApp();
  const [form, setForm] = useState(defaultForm);
  const [submitting, setSubmitting] = useState(false);
  const [requestError, setRequestError] = useState('');
  const [selected, setSelected] = useState(null);
  const [sort, setSort] = useState({ key: 'timestamp', direction: 'desc' });
  const [csvStatus, setCsvStatus] = useState('');
  const csvTimers = useRef([]);

  const sendTransaction = useCallback(async (payload, { automated = false } = {}) => {
    setSubmitting(true);
    setRequestError('');
    try {
      const result = await evaluateTransaction(payload);
      const entry = addTransaction({ ...payload, ...result, timestamp: new Date().toISOString() });
      if (result.is_blocked) {
        setNotice({ tone: 'danger', title: 'Transaction blocked', message: `${payload.card_id} exceeded the current model decision boundary.` });
        pollForAudit(audits.length);
      } else if (!automated) {
        setNotice({ tone: 'success', title: 'Transaction approved', message: `${payload.card_id} cleared the ensemble gate.` });
      }
      return entry;
    } catch (error) {
      setRequestError(error.message);
      if (!automated) setNotice({ tone: 'danger', title: 'Evaluation failed', message: error.message });
      return null;
    } finally {
      setSubmitting(false);
    }
  }, [addTransaction, audits.length, pollForAudit, setNotice]);

  const simulator = useTrafficSimulator(merchants, sendTransaction, health === 'online');
  const merchantOptions = useMemo(() => Object.entries(merchants).map(([id, item]) => ({ id, ...item })), [merchants]);
  const sortedTransactions = useMemo(() => [...transactions].sort((a, b) => {
    const left = a[sort.key] ?? '';
    const right = b[sort.key] ?? '';
    const comparison = typeof left === 'number' ? left - right : String(left).localeCompare(String(right));
    return sort.direction === 'asc' ? comparison : -comparison;
  }), [transactions, sort]);

  const setSortKey = (key) => setSort((current) => ({ key, direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc' }));
  const parentRef = useRef(null);
  const virtualizer = useVirtualizer({ count: sortedTransactions.length, getScrollElement: () => parentRef.current, estimateSize: () => 58, overscan: 8 });

  const submit = (event) => {
    event.preventDefault();
    if (!form.card_id.trim() || !form.device_id.trim() || !form.merchant_id.trim() || Number(form.amount_paise) <= 0) {
      setRequestError('Enter a positive amount and all transaction identifiers.');
      return;
    }
    sendTransaction({ ...form, amount_paise: Number(form.amount_paise) });
  };

  const handleCsv = (file) => {
    if (!file) return;
    csvTimers.current.forEach(window.clearTimeout);
    const reader = new FileReader();
    setCsvStatus('Reading transaction ledger…');
    reader.onload = () => {
      const rows = String(reader.result).trim().split(/\r?\n/).slice(1).map((line) => line.split(',')).filter((columns) => columns.length >= 4);
      if (!rows.length) { setCsvStatus('No valid transaction rows were found.'); return; }
      setCsvStatus(`Replaying ${rows.length} transactions with bounded sequencing.`);
      const play = async (index) => {
        if (index >= rows.length) { setCsvStatus(`Replay complete — ${rows.length} transactions submitted.`); return; }
        const [amount, card, device, merchant] = rows[index];
        await sendTransaction({ amount_paise: Number.parseInt(amount, 10) || 1200, card_id: card.trim() || 'csv_card', device_id: device.trim() || 'csv_device', merchant_id: merchant.trim() || '7995' }, { automated: true });
        csvTimers.current[index] = window.setTimeout(() => play(index + 1), 400);
      };
      play(0);
    };
    reader.onerror = () => setCsvStatus('The CSV could not be read. Check the file and try again.');
    reader.readAsText(file);
  };

  const simulatorLabel = { stopped: 'Stopped', running: 'Evaluating', waiting: 'Rate limited', offline: 'Paused — offline' }[simulator.status];

  return (
    <div className="page-stack">
      <section className={`status-band status-band--${health}`} aria-live="polite">
        <div><span className={`status-dot status-dot--${health}`} /><strong>{health === 'online' ? 'Decision pipeline operational' : 'Decision pipeline unavailable'}</strong><span>{health === 'online' ? 'Live evaluations and audit offloading are available.' : 'Start the backend risk core before submitting traffic.'}</span></div>
        <Badge tone={simulator.status === 'offline' ? 'critical' : simulator.status === 'stopped' ? 'neutral' : 'info'}>Simulator: {simulatorLabel}</Badge>
      </section>

      {(dataError || requestError) && <div className="inline-alert" role="alert"><AlertTriangle size={17} /><div><strong>Operational attention required</strong><p>{requestError || dataError}</p></div></div>}

      <section className="metric-grid" aria-label="Transaction metrics">
        <Metric label="Processed" value={stats.total} detail="Loaded ledger" />
        <Metric label="Approved" value={stats.approved} detail="Passed decision gate" tone="success" />
        <Metric label="Blocked" value={stats.blocked} detail="Requires review" tone="critical" />
        <Metric label="Approval rate" value={`${stats.approvalRate.toFixed(1)}%`} detail="Current loaded sample" tone="info" />
      </section>

      <div className="live-layout">
        <Panel title="Transaction forge" eyebrow="Evaluate" className="forge-panel">
          <form className="form-stack" onSubmit={submit}>
            <fieldset><legend>Risk profile</legend><div className="segmented-control">{Object.entries(presets).map(([key, value]) => <button type="button" key={key} onClick={() => setForm(value)}>{key === 'standard' ? 'Standard' : key === 'elevated' ? 'Elevated' : 'Ceiling breach'}</button>)}</div></fieldset>
            <label className="field"><span>Amount in paise</span><div className="input-with-value"><input type="number" min="1" max="1000000" value={form.amount_paise} onChange={(event) => setForm({ ...form, amount_paise: event.target.value })} /><output>{formatCurrency(Number(form.amount_paise))}</output></div></label>
            <div className="form-grid"><label className="field"><span>Card ID</span><input value={form.card_id} onChange={(event) => setForm({ ...form, card_id: event.target.value })} /></label><label className="field"><span>Device ID</span><input value={form.device_id} onChange={(event) => setForm({ ...form, device_id: event.target.value })} /></label></div>
            <label className="field"><span>Merchant category</span><input list="merchant-options" value={form.merchant_id} onChange={(event) => setForm({ ...form, merchant_id: event.target.value })} placeholder="Search code or category" /><datalist id="merchant-options">{merchantOptions.map((item) => <option key={item.id} value={item.id}>{item.category} · {item.risk_level}</option>)}</datalist><small>{merchants[form.merchant_id] ? `${merchants[form.merchant_id].category} · ${merchants[form.merchant_id].risk_level} risk` : 'Enter a merchant category code'}</small></label>
            <button className="button button--primary button--full" disabled={submitting || health !== 'online'}><Send size={16} />{submitting ? 'Evaluating transaction…' : 'Evaluate transaction'}</button>
            <div className="simulator-control"><div><strong>Automated traffic</strong><span>Sequential requests with backpressure</span></div>{simulator.status === 'stopped' ? <button type="button" className="button button--secondary" onClick={simulator.start} disabled={health !== 'online'}><Play size={15} />Start</button> : <button type="button" className="button button--secondary" onClick={simulator.stop}><CircleStop size={15} />Stop</button>}</div>
            <label className="csv-drop"><CloudUpload size={20} /><span><strong>Replay a CSV ledger</strong><small>amount_paise, card_id, device_id, merchant_id</small></span><input type="file" accept=".csv,text/csv" onChange={(event) => handleCsv(event.target.files?.[0])} /></label>
            {csvStatus && <p className="field-message" role="status">{csvStatus}</p>}
          </form>
        </Panel>

        <Panel title="Activity ledger" eyebrow="Live stream" className="ledger-panel" action={<span className="panel-count">{transactions.length} records</span>}>
          {transactions.length === 0 ? <EmptyState title="No transaction activity" message="Evaluate a transaction or start automated traffic to populate the ledger." /> : <div className="data-table" role="table" aria-label="Transaction activity">
            <div className="table-header" role="row">{[['timestamp','Time'],['card_id','Identity'],['merchant_id','MCC'],['amount_paise','Amount'],['ensemble_risk_score','Risk'],['is_blocked','Decision']].map(([key,label]) => <button key={key} role="columnheader" onClick={() => setSortKey(key)}>{label}<ArrowDownUp size={11} /></button>)}</div>
            <div className="virtual-table" ref={parentRef}><div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>{virtualizer.getVirtualItems().map((row) => { const item = sortedTransactions[row.index]; return <button key={item._key || `${item.timestamp}-${row.index}`} className={`table-row ${item.is_blocked ? 'table-row--blocked' : ''}`} style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: row.size, transform: `translateY(${row.start}px)` }} onClick={() => setSelected(item)} role="row"><span role="cell" className="mono">{formatTime(item.timestamp)}</span><span role="cell"><strong className="mono">{item.card_id}</strong><small className="mono">{item.device_id}</small></span><span role="cell" className="mono">{item.merchant_id}</span><span role="cell" className="mono">{formatCurrency(item.amount_paise)}</span><span role="cell" className="mono">{(Number(item.ensemble_risk_score) * 100).toFixed(2)}%</span><span role="cell"><Badge tone={item.is_blocked ? 'critical' : 'success'}>{item.is_blocked ? 'Blocked' : 'Approved'}</Badge><ChevronRight size={14} /></span></button>; })}</div></div>
          </div>}
        </Panel>
      </div>

      {selected && <div className="drawer-layer" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setSelected(null)}><aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="transaction-drawer-title"><header><div><span className="eyebrow">Transaction record</span><h2 id="transaction-drawer-title" className="mono">{selected.card_id}</h2></div><button className="icon-button" onClick={() => setSelected(null)} aria-label="Close transaction details"><X size={18} /></button></header><div className="drawer-content"><div className={`decision-summary ${selected.is_blocked ? 'decision-summary--blocked' : ''}`}>{selected.is_blocked ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}<div><strong>{selected.is_blocked ? 'Blocked by ensemble gate' : 'Approved by ensemble gate'}</strong><span className="mono">{(Number(selected.ensemble_risk_score) * 100).toFixed(3)}% model score</span></div></div><dl className="detail-list"><div><dt>Amount</dt><dd className="mono">{formatCurrency(selected.amount_paise)}</dd></div><div><dt>Device</dt><dd className="mono">{selected.device_id}</dd></div><div><dt>Merchant</dt><dd className="mono">{selected.merchant_id}</dd></div><div><dt>Evaluated</dt><dd className="mono">{new Date(selected.timestamp).toLocaleString()}</dd></div></dl><pre className="payload-block">{JSON.stringify(selected.hydrated_metrics || {}, null, 2)}</pre></div></aside></div>}
    </div>
  );
}
