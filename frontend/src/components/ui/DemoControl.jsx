import { useState } from 'react';
import { Activity, CircleStop, Play, Send, X, Zap } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Badge } from './Primitives';

const money = (value) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(value || 0) / 100);

export default function DemoControl() {
  const { demoControlOpen, setDemoControlOpen, demoStatus, demoScenario, demoEvents, startDemo, stopDemo, submitDemoTransaction, connectionStatus } = useApp();
  const [form, setForm] = useState({ amount_paise: 425000, card_id: 'recruiter_card_01', device_id: 'recruiter_device_ring', merchant_id: '7995' });
  if (!demoControlOpen) return null;
  return <div className="demo-layer" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setDemoControlOpen(false)}>
    <section className="demo-console" role="dialog" aria-modal="true" aria-label="Guided live demonstration">
      <header><div><span className="eyebrow">Recruiter demonstration</span><h2>Watch the complete decision pipeline</h2><p>Generate authenticated evaluations and observe the same events arrive through the live WebSocket channel.</p></div><button className="icon-button" onClick={() => setDemoControlOpen(false)} aria-label="Close live demo"><X size={18}/></button></header>
      <div className="demo-connection"><span className={`status-dot status-dot--${connectionStatus === 'connected' ? 'online' : 'offline'}`}/><strong>WebSocket {connectionStatus}</strong><span>{demoStatus === 'running' ? `${demoScenario.replaceAll('_', ' ')} is emitting transactions` : 'Traffic generator is stopped'}</span>{demoStatus === 'running' && <button onClick={stopDemo}><CircleStop size={14}/>Stop</button>}</div>
      <div className="demo-choices"><button onClick={() => startDemo('mixed')} className={demoStatus === 'running' && demoScenario === 'mixed' ? 'is-active' : ''}><Activity/><span><strong>Mixed live traffic</strong><small>Steady allowed traffic with recurring risk events.</small></span><Play/></button><button onClick={() => startDemo('fraud_burst')} className={demoStatus === 'running' && demoScenario === 'fraud_burst' ? 'is-active' : ''}><Zap/><span><strong>Fraud burst</strong><small>Rapid card and device reuse to exercise the block workflow.</small></span><Play/></button></div>
      <div className="demo-manual"><div><span className="eyebrow">Manual evaluation</span><h3>Inject one transaction</h3><p>Change any field, submit it, and follow its decision through the application.</p></div><form onSubmit={(event) => { event.preventDefault(); submitDemoTransaction(form, 'manual'); }}><label>Amount in paise<input type="number" value={form.amount_paise} onChange={(event) => setForm({ ...form, amount_paise: event.target.value })}/><small>{money(form.amount_paise)}</small></label><label>Card identity<input value={form.card_id} onChange={(event) => setForm({ ...form, card_id: event.target.value })}/></label><label>Device identity<input value={form.device_id} onChange={(event) => setForm({ ...form, device_id: event.target.value })}/></label><label>Merchant category<input value={form.merchant_id} onChange={(event) => setForm({ ...form, merchant_id: event.target.value })}/></label><button className="button button--primary"><Send size={15}/>Evaluate now</button></form></div>
      <div className="demo-pipeline"><span>HTTP evaluation</span><i/><span>Model decision</span><i/><span>WebSocket event</span><i/><span>Human review</span><i/><span>Audit record</span></div>
      <div className="demo-event-log"><header><strong>Recent demonstration events</strong><Badge tone={demoStatus === 'running' ? 'info' : 'neutral'}>{demoStatus}</Badge></header>{demoEvents.length ? demoEvents.map((event) => <div key={event.id}><span className={`event-pulse ${event.error ? 'is-error' : event.blocked ? 'is-blocked' : ''}`}/><code>{event.id}</code><span>{event.error || `${(event.score * 100).toFixed(3)}% risk`}</span><Badge tone={event.error || event.blocked ? 'critical' : 'neutral'}>{event.error ? 'error' : event.blocked ? 'blocked' : 'allowed'}</Badge></div>) : <p>Start a scenario or submit a transaction. Its live events will appear here.</p>}</div>
    </section>
  </div>;
}
