import { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Clock3, History, RotateCcw, Search, Send, UserCheck } from 'lucide-react';
import {
  assignReviewCase,
  fetchReviewCase,
  fetchReviewCases,
  fetchUsers,
  finalizeReviewCase,
  reopenReviewCase,
  returnReviewCase,
  submitReviewRecommendation,
} from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Badge, EmptyState, PageGuide } from './ui/Primitives';

const money = (value = 0) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value / 100);
const utc = (value) => value ? `${new Date(value).toLocaleString('en-GB', { timeZone: 'UTC', hour12: false })} UTC` : '—';
const words = (value = '') => value.replaceAll('_', ' ');
const stages = ['open', 'in_review', 'awaiting_approval', 'resolved'];

function Workflow({ status }) {
  const active = Math.max(0, stages.indexOf(status));
  return (
    <div className="case-workflow" aria-label={`Workflow stage ${words(status)}`}>
      {stages.map((stage, index) => (
        <div key={stage} className={index < active ? 'is-complete' : index === active ? 'is-current' : ''}>
          <i>{index < active ? '✓' : index + 1}</i>
          <span>
            <strong>{stage === 'open' ? 'Unassigned' : stage === 'in_review' ? 'Analyst review' : stage === 'awaiting_approval' ? 'Admin approval' : 'Finalized'}</strong>
            <small>{stage === 'open' ? 'Awaiting assignment' : stage === 'in_review' ? 'Evidence investigation' : stage === 'awaiting_approval' ? 'Recommendation submitted' : 'Decision recorded'}</small>
          </span>
        </div>
      ))}
    </div>
  );
}

function EvidenceBars({ shap = {} }) {
  const x = shap.xgb_normalized_impacts || shap.xgb_feature_impacts || {};
  const l = shap.lgb_normalized_impacts || shap.lgb_feature_impacts || {};
  const keys = [...new Set([...Object.keys(x), ...Object.keys(l)])].slice(0, 7);
  const max = Math.max(.001, ...keys.flatMap((key) => [Math.abs(Number(x[key] || 0)), Math.abs(Number(l[key] || 0))]));
  return (
    <div className="evidence-bars">
      {keys.map((key) => (
        <div key={key} tabIndex="0">
          <span>{words(key)}</span>
          <i>
            <b style={{ width: `${Math.abs(Number(x[key] || 0)) / max * 100}%` }} />
            <em style={{ width: `${Math.abs(Number(l[key] || 0)) / max * 100}%` }} />
          </i>
          <small className="mono"><strong>X</strong> {Number(x[key] || 0).toFixed(3)} · <strong>L</strong> {Number(l[key] || 0).toFixed(3)}</small>
          <output>
            <strong>{words(key)}</strong>
            <span>XGBoost contribution: {Number(x[key] || 0).toFixed(4)}</span>
            <span>LightGBM contribution: {Number(l[key] || 0).toFixed(4)}</span>
          </output>
        </div>
      ))}
    </div>
  );
}

function DecisionRecord({ detail }) {
  const recommendationAction = [...detail.actions].reverse().find((action) => ['recommendation_submitted', 'decision_submitted'].includes(action.action_type));
  const finalAction = [...detail.actions].reverse().find((action) => ['final_decision_submitted', 'overridden'].includes(action.action_type));
  return (
    <div className="decision-record">
      <div><span>Analyst recommendation</span><strong>{detail.analyst_recommendation ? words(detail.analyst_recommendation) : 'Not submitted'}</strong><p>{recommendationAction?.reason || 'The assigned analyst has not submitted a recommendation.'}</p><small>{recommendationAction ? utc(recommendationAction.created_at) : ''}</small></div>
      <i />
      <div><span>Administrator decision</span><strong>{detail.final_decision ? words(detail.final_decision) : 'Awaiting approval'}</strong><p>{finalAction?.reason || 'The final administrator decision has not been recorded.'}</p><small>{finalAction ? utc(finalAction.created_at) : ''}</small></div>
      {detail.final_decision && <Badge tone={detail.final_decision === detail.analyst_recommendation ? 'info' : 'warning'}>{detail.final_decision === detail.analyst_recommendation ? 'Recommendation approved' : 'Decision changed'}</Badge>}
    </div>
  );
}

function CaseHistory({ actions = [] }) {
  return (
    <section className="case-history">
      <h4><History size={15} /> Immutable case history</h4>
      {actions.map((action) => (
        <div key={action.id}>
          <i />
          <span>
            <strong>{words(action.action_type)}</strong>
            <small>{action.reason}</small>
            {action.decision && <Badge tone="neutral">{words(action.decision)}</Badge>}
            <em>{utc(action.created_at)} · version {action.case_version}</em>
          </span>
        </div>
      ))}
    </section>
  );
}

function CaseAction({ admin, detail, assignedToMe, users, assignee, setAssignee, decision, setDecision, reason, setReason, busy, act }) {
  if (!detail) return null;
  let title = detail.status === 'open' ? 'Assign an analyst' : detail.status === 'in_review' ? 'Analyst investigation' : detail.status === 'awaiting_approval' ? 'Record final decision' : 'Decision complete';

  return (
    <section className="embedded-case-action">
      <header>
        <div><span className="eyebrow">Required next action</span><h3>{title}</h3></div>
        <p>{detail.assigned_reviewer ? `Owned by ${detail.assigned_reviewer.full_name}` : 'No analyst is assigned'}</p>
      </header>

      {admin && detail.status === 'open' && <div className="decision-form">
        <label>Analyst<select value={assignee} onChange={(event) => setAssignee(event.target.value)}><option value="">Choose an active analyst</option>{users.filter((item) => item.role === 'analyst' && item.is_active).map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select></label>
        <label>Assignment context<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain the priority and requested investigation…" /></label>
        <button className="button button--primary" disabled={!assignee || reason.trim().length < 10 || busy} onClick={() => act(() => assignReviewCase(detail.id, { expected_version: detail.version, assigned_to_user_id: Number(assignee), reason }))}><UserCheck size={16} />Assign investigation</button>
      </div>}

      {admin && detail.status === 'in_review' && <div className="waiting-state"><Clock3 /><strong>Investigation in progress</strong><p>{detail.assigned_reviewer?.full_name} owns this case. Final-decision controls appear after their recommendation is submitted.</p></div>}

      {admin && detail.status === 'awaiting_approval' && <div className="decision-form">
        <label>Final verdict<select value={decision === 'needs_more_information' ? 'confirmed_fraud' : decision} onChange={(event) => setDecision(event.target.value)}><option value="confirmed_fraud">Confirmed fraud</option><option value="false_positive">False positive</option></select></label>
        <label>Administrator rationale<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain why the recommendation is approved or changed…" /></label>
        <button className="button button--primary" disabled={reason.trim().length < 10 || busy} onClick={() => act(() => finalizeReviewCase(detail.id, { expected_version: detail.version, decision: decision === 'needs_more_information' ? 'confirmed_fraud' : decision, reason }))}><CheckCircle2 size={16} />Record final decision</button>
        <button className="button button--secondary" disabled={reason.trim().length < 10 || busy} onClick={() => act(() => returnReviewCase(detail.id, { expected_version: detail.version, reason }))}><RotateCcw size={16} />Return for more evidence</button>
      </div>}

      {admin && detail.status === 'resolved' && <div className="decision-form">
        <div className="waiting-state"><CheckCircle2 /><strong>Final decision recorded</strong><p>This case is read-only. Reopening appends a new transition without changing the original history.</p></div>
        <label>Reopen rationale<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain why another investigation is required…" /></label>
        <button className="button button--secondary" disabled={reason.trim().length < 10 || busy} onClick={() => act(() => reopenReviewCase(detail.id, { expected_version: detail.version, reason }))}><RotateCcw size={16} />Reopen case</button>
      </div>}

      {!admin && detail.status === 'in_review' && assignedToMe && <div className="decision-form">
        <label>Recommendation<select value={decision} onChange={(event) => setDecision(event.target.value)}><option value="confirmed_fraud">Confirmed fraud</option><option value="false_positive">False positive</option><option value="needs_more_information">More evidence required</option></select></label>
        <label>Evidence-backed rationale<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Record the evidence behind your recommendation…" /></label>
        <button className="button button--primary" disabled={reason.trim().length < 10 || busy} onClick={() => act(() => submitReviewRecommendation(detail.id, { expected_version: detail.version, decision, reason }))}><Send size={16} />Submit recommendation</button>
        <small className="authority-note">An administrator must approve or change this recommendation before the case is resolved.</small>
      </div>}

      {!admin && detail.status === 'in_review' && !assignedToMe && <div className="waiting-state"><Clock3 /><strong>Assigned to another analyst</strong><p>This case is visible for context but cannot be changed from your account.</p></div>}
      {!admin && detail.status === 'open' && <div className="waiting-state"><Clock3 /><strong>Awaiting administrator assignment</strong><p>No analyst action is available until an administrator assigns this case.</p></div>}
      {!admin && detail.status === 'awaiting_approval' && <div className="waiting-state"><Clock3 /><strong>Recommendation submitted</strong><p>The case is waiting for an administrator to record the final verdict.</p></div>}
      {!admin && detail.status === 'resolved' && <div className="waiting-state"><CheckCircle2 /><strong>Administrator finalized</strong><p>Review the recommendation and final decision comparison above.</p></div>}
    </section>
  );
}

export default function IncidentCenter() {
  const { user } = useAuth();
  const admin = user?.role === 'admin';
  const [page, setPage] = useState({ items: [], total: 0 });
  const [detail, setDetail] = useState(null);
  const [status, setStatus] = useState('');
  const [priority, setPriority] = useState('');
  const [mine, setMine] = useState(!admin);
  const [query, setQuery] = useState('');
  const [decision, setDecision] = useState('confirmed_fraud');
  const [reason, setReason] = useState('');
  const [users, setUsers] = useState([]);
  const [assignee, setAssignee] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const queueFilters = useMemo(() => ({ status, priority, assigned_to_me: mine, limit: 100 }), [status, priority, mine]);
  const loadQueue = useCallback(async () => {
    try {
      setError('');
      const data = await fetchReviewCases(queueFilters);
      setPage(data);
      return data;
    } catch (requestError) {
      setError(requestError.message);
      return { items: [] };
    }
  }, [queueFilters]);

  useEffect(() => {
    let active = true;
    loadQueue().then(async (data) => {
      if (active && data.items[0]) setDetail(await fetchReviewCase(data.items[0].id));
    });
    return () => { active = false; };
  }, [loadQueue]);
  useEffect(() => { if (admin) fetchUsers().then(setUsers).catch(() => {}); }, [admin]);

  const open = async (item) => {
    setBusy(true);
    try {
      setDetail(await fetchReviewCase(item.id));
      setReason('');
      setAssignee(item.assigned_to_user_id ? String(item.assigned_to_user_id) : '');
      setError('');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };
  const act = async (action) => {
    if (!detail) return;
    setBusy(true);
    setError('');
    try {
      await action();
      setDetail(await fetchReviewCase(detail.id));
      await loadQueue();
      setReason('');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const visible = useMemo(() => page.items.filter((item) => `${item.transaction_id} ${item.id} ${item.assigned_reviewer?.full_name || ''}`.toLowerCase().includes(query.toLowerCase())), [page.items, query]);
  const transaction = detail?.transaction;
  const assignedToMe = detail?.assigned_to_user_id === user?.id;

  return (
    <div className="ops-page">
      <PageGuide title={admin ? 'Turn analyst recommendations into final decisions.' : 'Investigate assigned model decisions and submit evidence-backed recommendations.'}>
        {admin ? 'Assign open cases, monitor active investigations, and act only when a recommendation reaches approval.' : 'Your recommendation never closes the case. An administrator reviews it and records the final verdict.'}
      </PageGuide>
      <section className="ops-statusline">
        <div><strong>{admin ? 'Review control' : 'My investigation queue'}</strong></div>
        <span>{page.total} cases</span>
        <span>{page.items.filter((item) => item.status === 'open').length} unassigned</span>
        <span>{page.items.filter((item) => item.status === 'in_review').length} investigating</span>
        <span>{page.items.filter((item) => item.status === 'awaiting_approval').length} awaiting approval</span>
      </section>
      {error && <div className="ops-alert">{error}</div>}
      <section className="review-workbench">
        <aside className="review-queue">
          <div className="queue-tools">
            <label className="ops-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Case, transaction or analyst" /></label>
            <div>
              <select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Every stage</option><option value="open">Unassigned</option><option value="in_review">Analyst review</option><option value="awaiting_approval">Awaiting approval</option><option value="resolved">Resolved</option></select>
              <select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="">Every priority</option><option value="critical">Critical</option><option value="high">High</option></select>
            </div>
            {!admin && <label className="queue-check"><input type="checkbox" checked={mine} onChange={(event) => setMine(event.target.checked)} />Assigned to me</label>}
          </div>
          <div className="case-list">
            {visible.length ? visible.map((item) => (
              <button key={item.id} onClick={() => open(item)} className={detail?.id === item.id ? 'is-selected' : ''}>
                <i className={`priority-mark priority-${item.priority}`} />
                <span><strong>Case {String(item.id).padStart(4, '0')}</strong><small className="mono">{item.transaction_id}</small><em>{item.assigned_reviewer?.full_name || 'Unassigned'} · {words(item.status)}</em></span>
                <Badge tone={item.status === 'awaiting_approval' ? 'info' : item.priority === 'critical' ? 'critical' : 'warning'}>{item.status === 'awaiting_approval' ? 'approval' : item.priority}</Badge>
              </button>
            )) : <EmptyState title="Queue is clear" message="No cases match the active filters." />}
          </div>
        </aside>

        <main className="review-evidence">
          {detail && transaction ? <>
            <Workflow status={detail.status} />
            <header>
              <div><span className="eyebrow">Case {String(detail.id).padStart(4, '0')} · version {detail.version}</span><h2 className="mono">{transaction.transaction_id}</h2><p>{utc(transaction.timestamp)} · MCC {transaction.merchant_id}</p></div>
              <div className="review-score"><span>Ensemble risk</span><strong className="mono">{(transaction.ensemble_risk_score * 100).toFixed(3)}%</strong><Badge tone="critical">{detail.priority}</Badge></div>
            </header>
            <div className="evidence-facts">
              <div><span>Amount</span><strong>{money(transaction.amount_paise)}</strong></div>
              <div><span>Card</span><strong className="mono">{transaction.card_id}</strong></div>
              <div><span>Device</span><strong className="mono">{transaction.device_id}</strong></div>
              <div><span>Assigned analyst</span><strong>{detail.assigned_reviewer?.full_name || 'Not assigned'}</strong></div>
            </div>
            {['awaiting_approval', 'resolved'].includes(detail.status) && <DecisionRecord detail={detail} />}
            <section className="evidence-section"><div><span className="eyebrow">Interactive model comparison</span><h3>Signals that moved the ensemble decision</h3><p>Hover or focus a signal to compare both tree-model contributions.</p></div><EvidenceBars shap={transaction.shap_payload} /></section>
            <section className="evidence-section"><div><span className="eyebrow">Hydrated context</span><h3>Runtime evidence supplied to the models</h3></div><div className="signal-matrix">{Object.entries(transaction.hydrated_metrics || {}).map(([key, value]) => <div key={key}><span>{words(key)}</span><strong className="mono">{String(value)}</strong></div>)}</div></section>
            <CaseAction admin={admin} detail={detail} assignedToMe={assignedToMe} users={users} assignee={assignee} setAssignee={setAssignee} decision={decision} setDecision={setDecision} reason={reason} setReason={setReason} busy={busy} act={act} />
            <CaseHistory actions={detail.actions} />
          </> : <EmptyState title="Select a review case" message="Evidence, ownership, recommendation and final decision will appear here." />}
        </main>
      </section>
    </div>
  );
}
