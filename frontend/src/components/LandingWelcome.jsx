import { useEffect, useState } from 'react';
import { ArrowDown, ArrowRight, Binary, BrainCircuit, Check, ChevronRight, Database, Fingerprint, Github, Landmark, Linkedin, LockKeyhole, Network, ScanLine, ShieldCheck, Sparkles, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';

const traceSteps = [
  ['01', 'Receive', 'A transaction arrives with a stable correlation ID and six bounded risk features.'],
  ['02', 'Score', 'XGBoost and LightGBM evaluate the same evidence independently.'],
  ['03', 'Explain', 'Signed SHAP contributions expose the signals behind the score.'],
  ['04', 'Review', 'Flagged decisions enter a role-aware human workflow.'],
  ['05', 'Prove', 'The decision and its evidence become a hash-linked audit record.'],
];

const tracePanels = [
  { stage: 'receive', status: '6 dimensions hydrated', rows: [['amount', '₹42,780'], ['device', 'ring_04 · 8 cards'], ['velocity', '11 attempts / 10m']], next: 'score/ensemble' },
  { stage: 'score', status: 'estimators complete', rows: [['xgboost', '0.941'], ['lightgbm', '0.913'], ['ensemble', '0.927 · BLOCK']], next: 'explain/shap' },
  { stage: 'explain', status: 'signed evidence retained', rows: [['card velocity', '+0.82'], ['device reuse', '+0.67'], ['known history', '−0.31']], next: 'human_review/open' },
  { stage: 'review', status: 'case assigned', rows: [['owner', 'Maya Chen'], ['state', 'investigating'], ['version', '3 · optimistic lock']], next: 'decision/submit' },
  { stage: 'prove', status: 'continuity verified', rows: [['record', 'AUD_0002'], ['previous', '82f0c4a1…9d3e'], ['digest', 'f19a02b7…62ac']], next: 'chain/head' },
];

const modelImpacts = [
  ['Card velocity', 82, 'risk'],
  ['Device reuse', 67, 'risk'],
  ['Unknown merchant', 48, 'risk'],
  ['Transaction amount', 24, 'risk'],
  ['Known card history', 31, 'safe'],
];

function DecisionEngine() {
  return (
    <div className="decision-engine" aria-label="Animated ensemble fraud decision diagram">
      <svg viewBox="0 0 640 520" role="img">
        <defs>
          <filter id="softGlow"><feGaussianBlur stdDeviation="5" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          <linearGradient id="riskLine" x1="0" x2="1"><stop stopColor="#b995ff" /><stop offset="1" stopColor="#ff7058" /></linearGradient>
        </defs>
        <g className="engine-grid"><path d="M20 430 320 260 620 430 320 600Z" /><path d="M80 395 320 260 560 395" /><path d="M145 360 320 260 495 360" /><path d="M210 323 320 260 430 323" /></g>
        <path className="engine-path engine-path--base" d="M28 262H150C186 262 184 174 220 174H328" />
        <path className="engine-path engine-path--base" d="M150 262C186 262 184 350 220 350H328" />
        <path className="engine-path engine-path--risk" d="M328 174C390 174 378 262 430 262H608" />
        <path className="engine-path engine-path--risk" d="M328 350C390 350 378 262 430 262" />
        <circle className="engine-packet" cx="28" cy="262" r="6" />
        <g className="engine-input"><rect x="26" y="218" width="124" height="88" rx="2" /><text x="43" y="245">TX_7F2A</text><text x="43" y="271" className="engine-value">₹42,780</text><text x="43" y="289">DEVICE RING 04</text></g>
        <g className="engine-model"><rect x="218" y="130" width="112" height="88" rx="2" /><text x="235" y="157">XGBOOST</text><text x="235" y="190" className="engine-score">0.941</text></g>
        <g className="engine-model"><rect x="218" y="306" width="112" height="88" rx="2" /><text x="235" y="333">LIGHTGBM</text><text x="235" y="366" className="engine-score">0.913</text></g>
        <g className="engine-gate" filter="url(#softGlow)"><circle cx="430" cy="262" r="49" /><circle cx="430" cy="262" r="34" /><text x="407" y="257">RISK</text><text x="401" y="280">92.7%</text></g>
        <g className="engine-output"><rect x="510" y="218" width="104" height="88" rx="2" /><text x="529" y="244">ROUTE</text><text x="529" y="270" className="engine-blocked">REVIEW</text><text x="529" y="289">AUDIT OPEN</text></g>
        <g className="engine-orbit"><circle cx="430" cy="262" r="72" /><circle cx="430" cy="190" r="4" /></g>
      </svg>
      <div className="engine-caption"><span><i /> Live decision trace</span><span>Ensemble agreement</span></div>
    </div>
  );
}

export default function LandingWelcome() {
  const [activeTrace, setActiveTrace] = useState(0);
  const tracePanel = tracePanels[activeTrace];

  useEffect(() => {
    const revealTargets = document.querySelectorAll('.landing-new [data-reveal]');
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.18, rootMargin: '0px 0px -8% 0px' });

    revealTargets.forEach((target) => observer.observe(target));
    return () => observer.disconnect();
  }, []);

  return (
    <div className="landing-new">
      <header className="site-header">
        <Link to="/" className="site-brand"><span><Landmark size={18} /></span><strong>Sentinel Guard</strong></Link>
        <nav aria-label="Landing navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#human-review">Human review</a>
          <a href="#integrity">Integrity</a>
          <a href="#models">Models</a>
        </nav>
        <div className="site-header-actions"><Link to="/signin?mode=demo" className="header-cta">Sign in / Explore demo <ArrowRight size={14} /></Link></div>
      </header>

      <main>
        <section className="hero-new">
          <div className="hero-copy">
            <p className="landing-eyebrow"><span /> Human-verifiable fraud intelligence</p>
            <h1>Fraud decisions you can <em>inspect, review,</em> and prove.</h1>
            <p className="hero-deck">Sentinel Guard connects ensemble detection, explainable evidence, human judgment, and chain-linked audit records in one accountable risk system.</p>
            <div className="hero-actions"><Link to="/signin?mode=demo" className="landing-primary">Explore analyst demo <ArrowRight size={16} /></Link><a href="#how-it-works" className="landing-secondary">See how it works <ArrowDown size={15} /></a></div>
            <div className="hero-facts"><span><Check size={13} /> Two-model consensus</span><span><Check size={13} /> Append-only review history</span><span><Check size={13} /> Single-tenant by design</span></div>
          </div>
          <DecisionEngine />
        </section>

        <div className="proof-rail" data-reveal aria-label="Core system capabilities"><span>01 / XGBoost + LightGBM</span><span>02 / Six bounded features</span><span>03 / SHAP evidence</span><span>04 / Analyst + administrator</span><span>05 / SHA-256 audit continuity</span></div>

        <section className="problem-section" data-reveal>
          <p className="section-index">01 — The missing layer</p>
          <div><h2><span className="flow-line">A score can stop a payment.</span><br /><em className="flow-line flow-line--delay">It cannot defend the decision.</em></h2><p>Automated detection becomes operationally useful only when a person can understand the evidence, challenge the result, and prove what happened afterward.</p></div>
          <div className="problem-statement"><span>MODEL OUTPUT</span><strong>0.927</strong><i /><span>OPERATIONAL QUESTION</span><strong>Why—and who reviewed it?</strong></div>
        </section>

        <section className="trace-section" id="how-it-works" data-reveal>
          <div className="trace-intro"><p className="section-index">02 — One continuous decision</p><h2>Follow a transaction<br />from signal to proof.</h2><p>The interface preserves context through every handoff. There is no black box between detection, explanation, review, and evidence.</p></div>
          <div className="trace-body">
            <div className="trace-line" aria-hidden="true"><span style={{ '--active-step': activeTrace }} /></div>
            <ol>{traceSteps.map(([number, title, copy], index) => <li className={activeTrace === index ? 'is-active' : ''} key={number}><button type="button" onClick={() => setActiveTrace(index)} aria-pressed={activeTrace === index}><span>{number}</span><div><h3>{title}</h3><p>{copy}</p></div><ChevronRight size={18} /></button></li>)}</ol>
            <div className="trace-console" key={tracePanel.stage} aria-live="polite" aria-label={`${tracePanel.stage} decision trace`}><header><span><i /> TX_7F2A / {tracePanel.stage}</span><span>13:42:08.114 UTC</span></header><div className="console-stage"><span>STAGE {activeTrace + 1} OF 5</span><strong>{tracePanel.status}</strong></div>{tracePanel.rows.map(([label, value], index) => <div className={`console-row ${index === 2 ? 'console-row--strong' : ''}`} key={label}><span>{label}</span><code>{value}</code></div>)}<div className="console-row"><span>next</span><code>{tracePanel.next}</code></div><footer><ScanLine size={14} /> click a stage to inspect its evidence</footer></div>
          </div>
        </section>

        <section className="explain-section" data-reveal>
          <div className="explain-visual">
            <div className="explain-axis"><span>supports approval</span><i /><span>supports fraud</span></div>
            {modelImpacts.map(([label, value, tone]) => <div className={`impact-row impact-row--${tone}`} key={label}><span>{label}</span><div><i style={{ '--impact': `${value}%` }} /></div><output>{tone === 'risk' ? '+' : '−'}{value / 100}</output></div>)}
            <p>Signed relative contribution · example transaction</p>
          </div>
          <div className="explain-copy"><p className="section-index">03 — Explain the score</p><h2>Evidence before confidence.</h2><p>SHAP contributions show which signals pushed each model toward risk or safety. Analysts compare model agreement without losing the underlying transaction.</p><blockquote>“Card velocity and device reuse drove this decision—not the amount alone.”</blockquote></div>
        </section>

        <section className="human-section" id="human-review" data-reveal>
          <header><p className="section-index">04 — Human judgment</p><h2>Two roles. One accountable history.</h2><p>The case can change. Its history cannot.</p></header>
          <div className="role-flow">
            <div className="role-lane">
              <div className="role-label"><UserRound size={19} /><span><strong>Analyst</strong><small>Evidence and disposition</small></span></div>
              <div className="role-actions">
                <span><strong>Assigned</strong><small>Receive ownership</small></span><i><ArrowRight size={14} /></i>
                <span><strong>Investigate</strong><small>Review evidence</small></span><i><ArrowRight size={14} /></i>
                <span><strong>Recommend</strong><small>Record rationale</small></span><i><ArrowRight size={14} /></i>
                <span><strong>Await approval</strong><small>Preserve ownership</small></span>
              </div>
            </div>
            <div className="role-lane">
              <div className="role-label"><ShieldCheck size={19} /><span><strong>Administrator</strong><small>Coordination and control</small></span></div>
              <div className="role-actions">
                <span><strong>Assign</strong><small>Route ownership</small></span><i><ArrowRight size={14} /></i>
                <span><strong>Review</strong><small>Inspect recommendation</small></span><i><ArrowRight size={14} /></i>
                <span><strong>Return / finalize</strong><small>Exercise final authority</small></span><i><ArrowRight size={14} /></i>
                <span><strong>Verify</strong><small>Check audit continuity</small></span>
              </div>
            </div>
          </div>
          <div className="history-tape"><span>14:03 ASSIGNED · ADMIN</span><span>14:19 RECOMMENDATION_SUBMITTED · MAYA C.</span><span>14:22 FINAL_DECISION_SUBMITTED · ADMIN</span><span>14:22 AUDIT_LINKED · SYSTEM</span></div>
        </section>

        <section className="integrity-section" id="integrity" data-reveal>
          <div className="integrity-copy"><p className="section-index">05 — Verifiable continuity</p><h2>Every record points back.</h2><p>Each compliance memorandum includes the preceding digest. Verification recomputes the contents and walks the complete chain, exposing any broken link or altered record.</p><div className="verify-state"><Fingerprint size={21} /><span><strong>Chain integrity verified</strong><small>5 records checked · 0 issues</small></span></div></div>
          <div className="hash-chain" aria-label="Four linked audit records, from genesis to the current chain head">
            <div className="chain-node"><i>01</i><span><small>GENESIS ANCHOR</small><strong>Known starting digest</strong><code>00000000…0000</code></span></div>
            <div className="chain-connector"><span>stored as previous_hash</span></div>
            <div className="chain-node"><i>02</i><span><small>RECORD 001</small><strong>Contents + previous digest</strong><code>82f0c4a1…9d3e</code></span></div>
            <div className="chain-connector"><span>binds the next record</span></div>
            <div className="chain-node"><i>03</i><span><small>RECORD 002</small><strong>Recomputed and compared</strong><code>f19a02b7…62ac</code></span></div>
            <div className="chain-connector"><span>verified continuation</span></div>
            <div className="chain-node chain-node--head"><i><LockKeyhole size={14} /></i><span><small>CURRENT CHAIN HEAD</small><strong>No broken links detected</strong><code>cd881f40…ab17</code></span></div>
          </div>
        </section>

        <section className="monitor-section" data-reveal>
          <div className="monitor-copy"><p className="section-index">06 — Monitor the system</p><h2>A model is not finished when it ships.</h2><p>Administrators see prediction behaviour alongside human outcomes: blocked rate, score distribution, case coverage, false positives, resolution time, and population shift.</p></div>
          <div className="monitor-plot" aria-label="Example score distribution"><div className="plot-meta"><span>Score distribution</span><span>Current 24h / previous 24h</span></div><div className="plot-bars">{[32, 48, 39, 63, 84, 72, 51, 38, 27, 19, 34, 58].map((height, index) => <i key={index} style={{ '--bar': `${height}%`, '--delay': `${index * 60}ms` }} />)}</div><div className="plot-axis"><span>0.0</span><span>risk score</span><span>1.0</span></div><div className="plot-footer"><span><b>0.084</b> PSI · stable</span><span><b>7.4%</b> false-positive feedback</span><span><b>18m</b> median resolution</span></div></div>
        </section>

        <section className="models-section" id="models" data-reveal>
          <header><p className="section-index">07 — Architecture, not a logo wall</p><h2>Each component has one job.</h2></header>
          <div className="model-layers"><div><span>Decision</span><strong><i><Binary size={18} /></i>XGBoost + LightGBM</strong><p>Independent estimators combined through an equal-weight ensemble.</p></div><div><span>Explanation</span><strong><i><BrainCircuit size={18} /></i>SHAP</strong><p>Signed feature contributions retained with each transaction.</p></div><div><span>Application</span><strong><i><Database size={18} /></i>FastAPI + SQLite + Alembic</strong><p>Authenticated contracts, durable state, and reproducible schema changes.</p></div><div><span>Evidence</span><strong><i><Network size={18} /></i>Generated memorandum + SHA-256 chain</strong><p>Asynchronous memorandum generation with independently verifiable continuity.</p></div></div>
        </section>

        <section className="guide-section" data-reveal><div><p className="section-index">A guided first look</p><h2>Follow one case.<br />See every layer.</h2><p className="guide-deck">The seeded demo is a short investigation, not an empty dashboard tour. Start with one flagged payment and follow its evidence into a human decision and a verifiable record.</p><Link to="/signin?mode=demo" className="guide-link">Begin the 3-minute walkthrough <ArrowRight size={15} /></Link></div><ol><li><span>01</span><p><small>LIVE STREAM → INCIDENT</small><strong>Inspect the signal</strong>Open a flagged transaction, compare both model scores, and identify the signals that produced the block.</p></li><li><span>02</span><p><small>INCIDENT → HUMAN RECOMMENDATION</small><strong>Record the judgment</strong>Open Maya's assigned case, review its SHAP evidence, and submit a reasoned recommendation.</p></li><li><span>03</span><p><small>APPROVAL → AUDIT VAULT</small><strong>Exercise final authority</strong>Switch to the administrator view, approve or return the recommendation, then verify the resulting chain record.</p></li></ol></section>

        <section className="final-cta" data-reveal><div className="cta-radar" aria-hidden="true"><i /><i /><i /></div><Sparkles size={22} /><p>Disposable identities. Seeded evidence. No setup ritual.</p><h2><span>See the decisions—</span><br /><em>not just the interface.</em></h2><div><Link to="/signin?mode=demo" className="landing-primary">Explore the live demo <ArrowRight size={16} /></Link></div></section>
      </main>

      <footer className="site-footer">
        <Link to="/" className="site-brand"><span><Landmark size={17} /></span><strong>Sentinel Guard</strong></Link>
        <div className="footer-copy">
          <p>Single-tenant fraud intelligence · Explainable evidence · Human-verifiable decisions</p>
          <p className="footer-author">
            Designed and built by <strong>Richa Gupta</strong>
            <a href="https://github.com/Richa-2005/sentinel-guard" target="_blank" rel="noopener noreferrer" aria-label="Richa Gupta on GitHub">
              <Github size={14} />
            </a>
            <a href="https://www.linkedin.com/in/richa-gupta-cse" target="_blank" rel="noopener noreferrer" aria-label="Richa Gupta on LinkedIn">
              <Linkedin size={14} />
            </a>
          </p>
        </div>
        <div className="footer-links"><Link to="/signin">Sign in</Link><a href="#how-it-works">How it works</a></div>
      </footer>
    </div>
  );
}
