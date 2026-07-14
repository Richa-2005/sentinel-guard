import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { fetchAudits, fetchMerchants, fetchTransactions, pingBackend } from '../api/client';

const AppContext = createContext(null);

function transactionKey(entry) {
  return [entry.timestamp, entry.card_id, entry.device_id, entry.merchant_id, entry.amount_paise].join(':');
}

export function AppProvider({ children }) {
  const [transactions, setTransactions] = useState([]);
  const [audits, setAudits] = useState([]);
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
  const auditPollRef = useRef(null);

  const checkHealth = useCallback(async () => {
    const ok = await pingBackend();
    setHealth(ok ? 'online' : 'offline');
    return ok;
  }, []);

  const hydrate = useCallback(async () => {
    setLoading(true);
    setDataError('');
    const [txResult, auditResult, merchantResult] = await Promise.allSettled([
      fetchTransactions(), fetchAudits(), fetchMerchants(),
    ]);
    if (txResult.status === 'fulfilled') setTransactions(txResult.value || []);
    if (auditResult.status === 'fulfilled') setAudits(auditResult.value || []);
    if (merchantResult.status === 'fulfilled') setMerchants(merchantResult.value || {});

    const failed = [txResult, auditResult, merchantResult].filter((item) => item.status === 'rejected');
    if (failed.length) setDataError(failed[0].reason?.message || 'Some operational data could not be loaded.');
    setHealth(failed.length === 3 ? 'offline' : 'online');
    setLoading(false);
  }, []);

  useEffect(() => {
    hydrate();
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

  const addTransaction = useCallback((entry) => {
    const enriched = { ...entry, _key: transactionKey(entry) };
    setTransactions((previous) => [enriched, ...previous].slice(0, 200));
    return enriched;
  }, []);

  const refreshAudits = useCallback(async () => {
    const next = await fetchAudits();
    setAudits(next || []);
    return next || [];
  }, []);

  const pollForAudit = useCallback((initialCount) => {
    window.clearInterval(auditPollRef.current);
    let attempts = 0;
    auditPollRef.current = window.setInterval(async () => {
      attempts += 1;
      try {
        const next = await refreshAudits();
        if (next.length > initialCount) {
          window.clearInterval(auditPollRef.current);
          setNotice({ tone: 'success', title: 'Compliance record available', message: 'The latest chain-linked audit has been added to the vault.' });
        }
      } catch {
        // A later attempt can recover while the bounded poll remains active.
      }
      if (attempts >= 8) {
        window.clearInterval(auditPollRef.current);
        setNotice({ tone: 'warning', title: 'Audit still processing', message: 'The risk decision is saved, but the compliance report is not available yet.' });
      }
    }, 3000);
  }, [refreshAudits]);

  useEffect(() => () => window.clearInterval(auditPollRef.current), []);

  const blockedTransactions = useMemo(() => transactions.filter((item) => item.is_blocked), [transactions]);
  const stats = useMemo(() => {
    const total = transactions.length;
    const blocked = blockedTransactions.length;
    const approved = total - blocked;
    return { total, blocked, approved, approvalRate: total ? (approved / total) * 100 : 100 };
  }, [transactions, blockedTransactions]);

  const value = useMemo(() => ({
    transactions, blockedTransactions, audits, merchants, stats, health, loading, dataError,
    notice, auditSearch, selectedAuditId, commandOpen, sidebarCollapsed,
    setNotice, setAuditSearch, setSelectedAuditId, setCommandOpen, setSidebarCollapsed,
    addTransaction, refreshAudits, pollForAudit, hydrate, checkHealth,
  }), [
    transactions, blockedTransactions, audits, merchants, stats, health, loading, dataError,
    notice, auditSearch, selectedAuditId, commandOpen, sidebarCollapsed,
    addTransaction, refreshAudits, pollForAudit, hydrate, checkHealth,
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
}
