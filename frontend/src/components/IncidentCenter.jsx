import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowRight, FileSearch, Filter, Search, ShieldCheck } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { Badge, EmptyState, Panel } from './ui/Primitives';

const metricMeta = {
  card_vel_10m: ['Card velocity', 5],
  device_card_ratio_30m: ['Device / card ratio', 1],
  device_card_limit_crossed: ['Device card limit', 1],
  is_known_merchant: ['Known merchant', 1],
  is_off_hours_window: ['Off-hours window', 1],
};

const money = (value = 0) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value / 100);

const contributionKeys = [
  'amount_paise',
  'card_vel_10m',
  'device_card_ratio_30m',
  'device_card_limit_crossed',
  'is_known_merchant',
  'is_off_hours_window',
];

function normalizeModelImpacts(values = {}) {
  const total = Object.values(values).reduce((sum, value) => sum + Math.abs(Number(value) || 0), 0);
  return Object.fromEntries(Object.entries(values).map(([key, value]) => [
    key,
    total > 0 ? (Number(value) || 0) / total : 0,
  ]));
}

function SignalBar({ label, value, max = 1, alert }) {
  const width = Math.max(2, Math.min(100, (Number(value) / max) * 100));
  return <div className="signal-row"><div><span>{label}</span><strong className="mono">{Number(value).toFixed(3)}</strong></div><div className="signal-track"><span className={alert ? 'signal-fill signal-fill--critical' : 'signal-fill'} style={{ width: `${width}%` }} /></div></div>;
}

function ContributionComparison({ shap = {} }) {
  const xgb = shap.xgb_normalized_impacts || normalizeModelImpacts(shap.xgb_feature_impacts);
  const lgb = shap.lgb_normalized_impacts || normalizeModelImpacts(shap.lgb_feature_impacts);
  return <div className="contribution-list">{contributionKeys.map((key) => {
    const x = Number(xgb[key] || 0);
    const l = Number(lgb[key] || 0);
    const divergent = Math.sign(x) !== Math.sign(l) && Math.abs(x) > 0.01 && Math.abs(l) > 0.01;
    return <div className="contribution" key={key}><div className="contribution-title"><strong>{metricMeta[key]?.[0] || key.replaceAll('_', ' ')}</strong>{divergent && <Badge tone="warning">Divergence</Badge>}</div><div className="comparison-line"><span>XGB</span><div><i style={{ width: `${Math.abs(x) * 100}%` }} className={x >= 0 ? 'positive' : 'negative'} /></div><output className="mono">{x >= 0 ? '+' : ''}{(x * 100).toFixed(1)}%</output></div><div className="comparison-line"><span>LGB</span><div><i style={{ width: `${Math.abs(l) * 100}%` }} className={l >= 0 ? 'positive' : 'negative'} /></div><output className="mono">{l >= 0 ? '+' : ''}{(l * 100).toFixed(1)}%</output></div></div>;
  })}</div>;
}

export default function IncidentCenter() {
  const { blockedTransactions, loading, dataError, setAuditSearch, setSelectedAuditId } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [severity, setSeverity] = useState('all');
  const [merchant, setMerchant] = useState('all');
  const [selected, setSelected] = useState(null);

  const merchants = useMemo(() => [...new Set(blockedTransactions.map((item) => item.merchant_id))].sort(), [blockedTransactions]);
  const filtered = useMemo(() => blockedTransactions.filter((item) => {
    const matchesQuery = `${item.card_id} ${item.device_id}`.toLowerCase().includes(query.toLowerCase());
    const score = Number(item.ensemble_risk_score);
    const matchesSeverity = severity === 'all' || severity === 'high' && score >= 0.2 || severity === 'elevated' && score < 0.2;
    return matchesQuery && matchesSeverity && (merchant === 'all' || item.merchant_id === merchant);
  }), [blockedTransactions, query, severity, merchant]);

  useEffect(() => {
    const requested = location.state?.selectedKey;
    const next = requested ? blockedTransactions.find((item) => item._key === requested) : filtered[0];
    if (!selected || !blockedTransactions.includes(selected)) setSelected(next || null);
  }, [blockedTransactions, filtered, location.state, selected]);

  const openAudit = () => {
    setAuditSearch(selected.card_id);
    setSelectedAuditId(null);
    navigate('/app/vault');
  };

  return (
    <div className="page-stack">
      <section className="incident-summary"><div><span className="summary-icon"><AlertTriangle size={20} /></span><div><strong>{blockedTransactions.length} blocked transactions</strong><p>Prioritized model decisions in the currently loaded ledger.</p></div></div><div className="summary-meta"><span>Highest observed score</span><strong className="mono">{blockedTransactions.length ? `${(Math.max(...blockedTransactions.map((item) => Number(item.ensemble_risk_score))) * 100).toFixed(2)}%` : '—'}</strong></div></section>

      <div className="incident-layout">
        <Panel title="Incident queue" eyebrow="Triage" className="incident-queue" action={<Badge tone="critical">{filtered.length} visible</Badge>}>
          <div className="filter-stack">
            <label className="search-field"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search card or device" aria-label="Search incident queue" /></label>
            <div className="filter-row"><label><Filter size={14} /><span className="sr-only">Severity</span><select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">All severities</option><option value="high">High · 20%+</option><option value="elevated">Elevated · below 20%</option></select></label><label><span className="sr-only">Merchant</span><select value={merchant} onChange={(event) => setMerchant(event.target.value)}><option value="all">All merchants</option>{merchants.map((id) => <option key={id} value={id}>MCC {id}</option>)}</select></label></div>
          </div>
          <div className="incident-list">
            {loading ? <div className="list-loading"><span className="skeleton" /><span className="skeleton" /><span className="skeleton" /></div> : dataError && !blockedTransactions.length ? <EmptyState error title="Incident data unavailable" message={dataError} /> : !filtered.length ? <EmptyState title="No matching incidents" message="Adjust the search or filters to broaden the queue." /> : filtered.map((item) => <button key={item._key || `${item.timestamp}-${item.card_id}`} className={`incident-item ${selected === item ? 'incident-item--selected' : ''}`} onClick={() => setSelected(item)}><span className="severity-marker" aria-hidden="true" /><div><strong className="mono">{item.card_id}</strong><small className="mono">{item.device_id}</small><span>{new Date(item.timestamp).toLocaleString()}</span></div><div><strong className="mono">{(Number(item.ensemble_risk_score) * 100).toFixed(2)}%</strong><small className="mono">{money(item.amount_paise)}</small><ArrowRight size={14} /></div></button>)}
          </div>
        </Panel>

        <Panel className="incident-detail">
          {!selected ? <EmptyState title="Select an incident" message="Choose a blocked transaction from the queue to inspect its evidence." action={<ShieldCheck size={18} />} /> : <div className="investigation">
            <header className="investigation-header"><div><span className="eyebrow">Blocked transaction</span><h2 className="mono">{selected.card_id}</h2><p className="mono">{selected.device_id} · MCC {selected.merchant_id}</p></div><div className="risk-score"><span>Ensemble risk</span><strong className="mono">{(Number(selected.ensemble_risk_score) * 100).toFixed(3)}%</strong><Badge tone="critical">Blocked</Badge></div></header>
            <div className="decision-context"><div><span>Amount</span><strong className="mono">{money(selected.amount_paise)}</strong></div><div><span>Evaluated</span><strong className="mono">{new Date(selected.timestamp).toLocaleString()}</strong></div><div><span>Merchant</span><strong className="mono">{selected.merchant_id}</strong></div></div>
            <section className="investigation-section"><div className="section-heading"><div><span className="eyebrow">Enrichment signals</span><h3>Hydrated risk indicators</h3></div></div><div className="signals-grid">{Object.entries(metricMeta).map(([key, [label, max]]) => { const value = Number(selected.hydrated_metrics?.[key] || 0); const alert = key === 'card_vel_10m' ? value >= 3 : key === 'is_known_merchant' ? value === 0 : value > 0.5; return <SignalBar key={key} label={label} value={value} max={max} alert={alert} />; })}</div></section>
            <section className="investigation-section"><div className="section-heading"><div><span className="eyebrow">Model evidence</span><h3>XGBoost and LightGBM contributions</h3></div><p>Signed relative share within each model. Compare direction and importance, not raw magnitude.</p></div><ContributionComparison shap={selected.shap_payload} /></section>
            <details className="payload-disclosure"><summary>Raw transaction payload</summary><pre>{JSON.stringify({ card_id: selected.card_id, device_id: selected.device_id, merchant_id: selected.merchant_id, amount_paise: selected.amount_paise, ensemble_risk_score: selected.ensemble_risk_score, hydrated_metrics: selected.hydrated_metrics, shap_payload: selected.shap_payload }, null, 2)}</pre></details>
            <button className="button button--primary" onClick={openAudit}><FileSearch size={16} />Open related audit records</button>
          </div>}
        </Panel>
      </div>
    </div>
  );
}
