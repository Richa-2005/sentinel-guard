import { useEffect, useMemo, useState } from 'react';
import { Search, Shield, UserRound } from 'lucide-react';
import { fetchReviewerSummaries, fetchUsers, updateUserRole, updateUserStatus } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Badge, EmptyState } from './ui/Primitives';

export default function PeopleAccess() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const [summaries, setSummaries] = useState([]);

  const load = () => Promise.all([fetchUsers(), fetchReviewerSummaries()])
    .then(([items, reviewerSummaries]) => {
      setUsers(items);
      setSummaries(reviewerSummaries);
      setSelected((current) => items.find((item) => item.id === current?.id) || items[0] || null);
    })
    .catch((requestError) => setError(requestError.message));

  useEffect(() => { load(); }, []);

  const visible = useMemo(() => users.filter((item) => `${item.full_name} ${item.email} ${item.role}`
    .toLowerCase().includes(query.toLowerCase())), [users, query]);
  const change = async (action) => {
    try { await action(); await load(); setError(''); } catch (requestError) { setError(requestError.message); }
  };
  const selectedSummary = summaries.find((item) => item.user_id === selected?.id);

  return <div className="ops-page">
    <section className="ops-statusline"><div><Shield size={14}/><strong>Two-role access boundary</strong></div><span>{users.length} identities</span><span>{users.filter((item) => item.is_active).length} active</span><span>{users.filter((item) => item.role === 'admin').length} administrators</span></section>
    {error && <div className="ops-alert">{error}</div>}
    <section className="access-workspace"><main><header><div><span className="eyebrow">Identity register</span><h2>People & access</h2></div><label className="ops-search"><Search size={14}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search identities"/></label></header><div className="user-head"><span>Identity</span><span>Role</span><span>Status</span><span>Created</span></div><div className="user-list">{visible.length ? visible.map((item) => <button key={item.id} className={selected?.id === item.id ? 'is-selected' : ''} onClick={() => setSelected(item)}><span><i><UserRound size={15}/></i><b>{item.full_name}<small>{item.email}</small></b></span><Badge tone={item.role === 'admin' ? 'info' : 'neutral'}>{item.role}</Badge><Badge tone={item.is_active ? 'neutral' : 'critical'}>{item.is_active ? 'active' : 'disabled'}</Badge><span>{new Date(item.created_at).toLocaleDateString('en-GB')}</span></button>) : <EmptyState title="No identities" message="No user matches this search."/>}</div></main>
      <aside><span className="eyebrow">Access inspector</span><h3>{selected?.full_name || 'Select an identity'}</h3>{selected && <><p>{selected.email}</p>{selected.role === 'analyst' && <div className="reviewer-summary"><div><span>Assigned</span><strong>{selectedSummary?.assigned_cases ?? 0}</strong></div><div><span>Recommendations</span><strong>{selectedSummary?.recommendations_submitted ?? 0}</strong></div><div><span>Finalized</span><strong>{selectedSummary?.finalized_cases ?? 0}</strong></div><div><span>Agreement</span><strong>{selectedSummary?.agreement_rate == null ? '—' : `${(selectedSummary.agreement_rate * 100).toFixed(0)}%`}</strong></div></div>}<dl className="ops-dl"><div><dt>User ID</dt><dd>{selected.id}</dd></div><div><dt>Last updated</dt><dd>{new Date(selected.updated_at).toLocaleString('en-GB')}</dd></div>{selectedSummary?.average_resolution_seconds != null && <div><dt>Average case</dt><dd>{Math.round(selectedSummary.average_resolution_seconds / 60)} minutes</dd></div>}</dl><label>Role<select value={selected.role} disabled={selected.id === me?.id} onChange={(event) => change(() => updateUserRole(selected.id, event.target.value))}><option value="analyst">Analyst</option><option value="admin">Administrator</option></select></label><button className={`button ${selected.is_active ? 'button--secondary' : 'button--primary'}`} disabled={selected.id === me?.id} onClick={() => change(() => updateUserStatus(selected.id, !selected.is_active))}>{selected.is_active ? 'Disable account' : 'Restore account'}</button>{selected.id === me?.id && <small className="self-protection">Your own administrator role and access cannot be removed.</small>}</>}</aside>
    </section>
  </div>;
}
