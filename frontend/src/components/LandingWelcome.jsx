import { Activity, ArrowRight, BarChart3, CheckCircle2, FileCheck2, Landmark, RefreshCw, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';

const workflows = [
  { icon: Activity, step: '01', title: 'Real-time decisioning', text: 'Evaluate live and replayed payment traffic through the existing dual-model risk gate.' },
  { icon: BarChart3, step: '02', title: 'Explainable investigation', text: 'Compare feature signals and model contributions without losing the transaction context.' },
  { icon: FileCheck2, step: '03', title: 'Compliance continuity', text: 'Follow blocked decisions into chain-linked regulatory records and operational evidence.' },
];

export default function LandingWelcome() {
  const { stats, health, loading, dataError, hydrate } = useApp();

  return (
    <div className="landing">
      <header className="landing-header">
        <Link to="/" className="landing-brand"><span className="brand-mark"><Landmark size={18} /></span><span><strong>Sentinel Guard</strong><small>Autonomous risk operations</small></span></Link>
        <div className="landing-status"><span className={`status-dot status-dot--${health}`} /><span>{health === 'online' ? 'Risk core operational' : health === 'checking' ? 'Checking risk core' : 'Risk core unavailable'}</span></div>
      </header>

      <main className="landing-main">
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-kicker"><ShieldCheck size={15} /> Financial threat decisioning</div>
          <h1 id="landing-title">A clearer operating picture for every risk decision.</h1>
          <p>Sentinel Guard brings transaction telemetry, ensemble-model evidence, and compliance records into one disciplined fraud-operations workspace.</p>
          <div className="landing-actions">
            <Link to="/app/live" className="button button--primary">Enter operations workspace <ArrowRight size={16} /></Link>
            <button className="button button--secondary" onClick={hydrate} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''} />Refresh system snapshot</button>
          </div>
          {dataError && <p className="landing-warning">Live operational data is temporarily unavailable. You can still enter the workspace.</p>}
        </section>

        <section className="landing-snapshot" aria-label="Live operational snapshot">
          <div className="snapshot-heading"><span>Operational snapshot</span><small>{loading ? 'Synchronizing' : 'Current loaded ledger'}</small></div>
          <div className="snapshot-grid">
            <div><span>Transactions</span><strong>{loading ? '—' : stats.total}</strong></div>
            <div><span>Approved</span><strong>{loading ? '—' : stats.approved}</strong></div>
            <div><span>Blocked</span><strong className="text-critical">{loading ? '—' : stats.blocked}</strong></div>
            <div><span>Approval rate</span><strong>{loading ? '—' : `${stats.approvalRate.toFixed(1)}%`}</strong></div>
          </div>
          <div className="snapshot-foot"><CheckCircle2 size={15} /><span>Data remains within your existing Sentinel Guard environment.</span></div>
        </section>

        <section className="architecture-strip" aria-label="Sentinel Guard processing architecture">
          {['Transaction', 'Ensemble gate', 'SHAP evidence', 'Compliance audit'].map((item, index) => <div key={item}><span>{String(index + 1).padStart(2, '0')}</span><strong>{item}</strong>{index < 3 && <ArrowRight size={15} aria-hidden="true" />}</div>)}
        </section>

        <section className="workflow-section" aria-labelledby="workflow-title">
          <div className="section-intro"><span className="eyebrow">One continuous workflow</span><h2 id="workflow-title">Built for the handoffs that define risk operations.</h2><p>Move from detection to investigation to evidence without switching mental models.</p></div>
          <div className="workflow-grid">{workflows.map(({ icon: Icon, step, title, text }) => <article key={title}><div className="workflow-icon"><Icon size={19} /><span>{step}</span></div><h3>{title}</h3><p>{text}</p></article>)}</div>
        </section>
      </main>

      <footer className="landing-footer"><span>Sentinel Guard</span><span>Ensemble risk · Explainable evidence · Chain-linked records</span></footer>
    </div>
  );
}
