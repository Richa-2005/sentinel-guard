import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { fetchAuditJobs, fetchAudits, fetchMerchants, fetchTransactions, pingBackend } from '../api/client';
import useWebSocketStream from '../hooks/useWebSocketStream';

const AppContext = createContext(null);
const MAX_TRANSACTIONS = 200;
const AUDIT_POLL_INTERVAL = 3000;
const AUDIT_POLL_TIMEOUT = 90000;

function transactionKey(entry) {
  return entry.transaction_id || [entry.timestamp, entry.card_id, entry.device_id, entry.merchant_id, entry.amount_paise].join(':');
}

function mergeTransactions(previous, incoming) {
  const merged = [...previous];

  incoming.forEach((entry) => {
    const key = transactionKey(entry);
    const existingIndex = merged.findIndex((item) => transactionKey(item) === key);
    const enriched = { ...entry, _key: key };

    if (existingIndex >= 0) {
      const existing = merged[existingIndex];
      merged.splice(existingIndex, 1);
      merged.unshift({
        ...existing,
        ...enriched,
        timestamp: entry.timestamp || existing.timestamp,
        _key: key,
      });
    } else {
      merged.unshift(enriched);
    }
  });

  return merged
    .sort((left, right) => new Date(right.timestamp || 0) - new Date(left.timestamp || 0))
    .slice(0, MAX_TRANSACTIONS);
}

function auditStatusFromRecords(records) {
  return records.reduce((statuses, record) => {
    const id = record.transaction_id || record.id;
    if (id) statuses[id] = { status: record.is_error ? 'failed' : 'complete', updatedAt: Date.now() };
    return statuses;
  }, {});
}

function normalizeAuditJobStatus(status) {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'pending' || normalized === 'processing') return 'processing';
  if (normalized === 'completed') return 'complete';
  if (normalized === 'failed') return 'failed';
  return 'delayed';
}

function auditStatusFromJobs(jobs) {
  return jobs.reduce((statuses, job) => {
    if (!job.transaction_id) return statuses;
    const startedAt = Date.parse(job.started_at || job.created_at || '');
    statuses[job.transaction_id] = {
      status: normalizeAuditJobStatus(job.status),
      attempts: job.attempts || 0,
      nextAttemptAt: job.next_attempt_at || null,
      lastError: job.last_error || null,
      startedAt: Number.isNaN(startedAt) ? Date.now() : startedAt,
      updatedAt: Date.now(),
    };
    return statuses;
  }, {});
}

export function AppProvider({ children }) {
  const [transactions, setTransactions] = useState([]);
  const [audits, setAudits] = useState([]);
  const [auditStatuses, setAuditStatuses] = useState({});
  const [merchants, setMerchants] = useState({});
  const [health, setHealth] = useState('checking');
  const [loading, setLoading] = useState(true);
  const [dataError, setDataError] = useState('');
  const [notice, setNotice] = useState(null);
  const [auditSearch, setAuditSearch] = useState('');
  const [selectedAuditId, setSelectedAuditId] = useState(null);
  const [commandOpen, setCommandOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem('sentinel-sidebar-collapsed') === 'true'
  );
  const initialHydrateStartedRef = useRef(false);

  const checkHealth = useCallback(async () => {
    const ok = await pingBackend();
    setHealth(ok ? 'online' : 'offline');
    return ok;
  }, []);

  const applyAudits = useCallback((records) => {
    const next = records || [];
    setAudits(next);
    setAuditStatuses((previous) => ({ ...previous, ...auditStatusFromRecords(next) }));
    return next;
  }, []);

  const applyAuditJobs = useCallback((jobs) => {
    setAuditStatuses((previous) => ({ ...previous, ...auditStatusFromJobs(jobs || []) }));
    return jobs || [];
  }, []);

  const refreshAudits = useCallback(async () => {
    const [records, jobs] = await Promise.all([fetchAudits(), fetchAuditJobs()]);
    applyAudits(records);
    applyAuditJobs(jobs);
    return records || [];
  }, [applyAuditJobs, applyAudits]);

  const addTransaction = useCallback((entry) => {
    const enriched = { ...entry, _key: transactionKey(entry) };
    setTransactions((previous) => mergeTransactions(previous, [enriched]));
    return enriched;
  }, []);

  const queueAudit = useCallback((transactionId) => {
    if (!transactionId) return;
    setAuditStatuses((previous) => ({
      ...previous,
      [transactionId]: {
        status: previous[transactionId]?.status === 'complete' ? 'complete' : 'processing',
        startedAt: previous[transactionId]?.startedAt || Date.now(),
        updatedAt: Date.now(),
      },
    }));
  }, []);

  const handleTransaction = useCallback((entry) => {
    addTransaction(entry);
    if (entry.is_blocked) queueAudit(entry.transaction_id);
  }, [addTransaction, queueAudit]);

  const handleAuditEvent = useCallback(async (event) => {
    const transactionId = event.transaction_id || event.id;
    if (!transactionId) return;

    setAuditStatuses((previous) => ({
      ...previous,
      [transactionId]: { status: event.status, updatedAt: Date.now() },
    }));

    try {
      await refreshAudits();
    } catch {
      // The bounded fallback checker will reconcile a briefly delayed audit index.
    }

    setNotice(event.status === 'failed'
      ? { tone: 'warning', title: 'Audit generation issue', message: `The risk decision is retained, but audit ${transactionId} did not complete.` }
      : event.status === 'processing'
        ? { tone: 'warning', title: 'Audit retry scheduled', message: `Audit ${transactionId} will retry automatically.` }
        : { tone: 'success', title: 'Compliance record available', message: `Audit ${transactionId} is now available in the vault.` });
  }, [refreshAudits]);

  const resyncAfterReconnect = useCallback(async () => {
    const [txResult, auditResult, jobResult] = await Promise.allSettled([
      fetchTransactions(), fetchAudits(), fetchAuditJobs(),
    ]);
    if (txResult.status === 'fulfilled') setTransactions((previous) => mergeTransactions(previous, txResult.value || []));
    if (auditResult.status === 'fulfilled') applyAudits(auditResult.value);
    if (jobResult.status === 'fulfilled') applyAuditJobs(jobResult.value);
  }, [applyAuditJobs, applyAudits]);

  const stream = useWebSocketStream({
    onTransaction: handleTransaction,
    onAuditEvent: handleAuditEvent,
    onReconnect: resyncAfterReconnect,
  });

  const hydrate = useCallback(async () => {
    setLoading(true);
    setDataError('');
    const [txResult, auditResult, jobResult, merchantResult] = await Promise.allSettled([
      fetchTransactions(), fetchAudits(), fetchAuditJobs(), fetchMerchants(),
    ]);
    if (txResult.status === 'fulfilled') setTransactions((previous) => mergeTransactions(previous, txResult.value || []));
    if (auditResult.status === 'fulfilled') applyAudits(auditResult.value);
    if (jobResult.status === 'fulfilled') applyAuditJobs(jobResult.value);
    if (merchantResult.status === 'fulfilled') setMerchants(merchantResult.value || {});

    const failed = [txResult, auditResult, jobResult, merchantResult].filter((item) => item.status === 'rejected');
    if (failed.length) setDataError(failed[0].reason?.message || 'Some operational data could not be loaded.');
    setHealth(failed.length === 4 ? 'offline' : 'online');
    setLoading(false);
  }, [applyAuditJobs, applyAudits]);

  useEffect(() => {
    if (!initialHydrateStartedRef.current) {
      initialHydrateStartedRef.current = true;
      hydrate();
    }
    const timer = window.setInterval(checkHealth, 30000);
    return () => window.clearInterval(timer);
  }, [hydrate, checkHealth]);

  useEffect(() => {
    localStorage.setItem('sentinel-sidebar-collapsed', String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setCommandOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const processingAuditIds = useMemo(() => Object.entries(auditStatuses)
    .filter(([, state]) => state.status === 'processing')
    .map(([id]) => id), [auditStatuses]);

  useEffect(() => {
    if (!processingAuditIds.length) return undefined;
    let cancelled = false;

    const checkPendingAudits = async () => {
      try {
        const records = await refreshAudits();
        if (cancelled) return;
        const available = new Set(records.map((record) => record.transaction_id || record.id));
        const completed = processingAuditIds.filter((id) => available.has(id));
        if (completed.length) {
          setNotice({ tone: 'success', title: 'Compliance record available', message: 'A pending chain-linked audit has been added to the vault.' });
        }
        setAuditStatuses((previous) => {
          const next = { ...previous };
          processingAuditIds.forEach((id) => {
            if (available.has(id)) {
              next[id] = { status: 'complete', updatedAt: Date.now() };
            } else if (Date.now() - (previous[id]?.startedAt || Date.now()) >= AUDIT_POLL_TIMEOUT) {
              next[id] = { ...previous[id], status: 'delayed', updatedAt: Date.now() };
            }
          });
          return next;
        });
      } catch {
        // WebSocket delivery remains primary; transient polling failures are non-fatal.
      }
    };

    const timer = window.setInterval(checkPendingAudits, AUDIT_POLL_INTERVAL);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [processingAuditIds.join('|'), refreshAudits]);

  const blockedTransactions = useMemo(() => transactions.filter((item) => item.is_blocked), [transactions]);
  const stats = useMemo(() => {
    const total = transactions.length;
    const blocked = blockedTransactions.length;
    const approved = total - blocked;
    return { total, blocked, approved, approvalRate: total ? (approved / total) * 100 : 100 };
  }, [transactions, blockedTransactions]);

  const value = useMemo(() => ({
    transactions, blockedTransactions, audits, auditStatuses, merchants, stats, health, loading, dataError,
    notice, auditSearch, selectedAuditId, commandOpen, sidebarCollapsed,
    liveStream: stream.liveStream, connectionStatus: stream.connectionStatus,
    lastEventAt: stream.lastEventAt, reconnectAttempt: stream.reconnectAttempt, streamError: stream.streamError,
    setNotice, setAuditSearch, setSelectedAuditId, setCommandOpen, setSidebarCollapsed,
    addTransaction, queueAudit, refreshAudits, hydrate, checkHealth,
    connectStream: stream.connect, disconnectStream: stream.disconnect,
  }), [
    transactions, blockedTransactions, audits, auditStatuses, merchants, stats, health, loading, dataError,
    notice, auditSearch, selectedAuditId, commandOpen, sidebarCollapsed, stream.liveStream,
    stream.connectionStatus, stream.lastEventAt, stream.reconnectAttempt, stream.streamError,
    setNotice, setAuditSearch, setSelectedAuditId, setCommandOpen, setSidebarCollapsed,
    addTransaction, queueAudit, refreshAudits, hydrate, checkHealth, stream.connect, stream.disconnect,
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
}
