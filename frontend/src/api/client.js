import { getAccessToken } from '../auth/session';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const DEFAULT_TIMEOUT = 12000;

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'REQUEST_FAILED', details = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request(path, { timeout = DEFAULT_TIMEOUT, signal, ...options } = {}) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort('timeout'), timeout);
  const abort = () => controller.abort(signal?.reason || 'cancelled');
  signal?.addEventListener('abort', abort, { once: true });

  try {
    const token = getAccessToken();
    const headers = new Headers(options.headers || {});
    if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(path, { ...options, headers, signal: controller.signal });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = Array.isArray(body?.detail)
        ? body.detail.map((item) => item?.msg).filter(Boolean).join('. ')
        : body?.detail;
      throw new ApiError(typeof detail === 'string' ? detail : `Request failed with status ${response.status}`, {
        status: response.status,
        code: response.status === 422 ? 'VALIDATION_ERROR' : 'HTTP_ERROR',
        details: body,
      });
    }
    return body;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      const timedOut = controller.signal.reason === 'timeout';
      throw new ApiError(timedOut ? 'The request timed out. Try again.' : 'The request was cancelled.', {
        code: timedOut ? 'TIMEOUT' : 'CANCELLED',
      });
    }
    throw new ApiError('Unable to reach Sentinel Guard. Check that the risk core is running.', {
      code: 'NETWORK_ERROR',
    });
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}

export function evaluateTransaction(payload, options = {}) {
  return request(`${API_BASE}/evaluate`, {
    ...options,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export const fetchTransactions = (options) => request(`${API_BASE}/transactions`, options);
export const fetchAudits = (options) => request(`${API_BASE}/audits`, options);
export const fetchAuditJobs = (options) => request(`${API_BASE}/audit-jobs`, options);
export const fetchMerchants = (options) => request(`${API_BASE}/merchants`, options);
export const verifyAuditChain = (options) => request(`${API_BASE}/audits/verify`, options);

export function fetchReviewCases(filters = {}, options = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined && value !== false) params.set(key, String(value));
  });
  return request(`${API_BASE}/reviews${params.size ? `?${params}` : ''}`, options);
}
export const fetchReviewCase = (caseId, options) => request(`${API_BASE}/reviews/${caseId}`, options);
const postReviewAction = (caseId, action, payload) => request(`${API_BASE}/reviews/${caseId}/${action}`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
});
export const claimReviewCase = (caseId, expectedVersion) => postReviewAction(caseId, 'claim', { expected_version: expectedVersion });
export const submitReviewRecommendation = (caseId, payload) => postReviewAction(caseId, 'recommendation', payload);
export const assignReviewCase = (caseId, payload) => postReviewAction(caseId, 'assign', payload);
export const reopenReviewCase = (caseId, payload) => postReviewAction(caseId, 'reopen', payload);
export const overrideReviewCase = (caseId, payload) => postReviewAction(caseId, 'override', payload);
export const finalizeReviewCase = (caseId, payload) => postReviewAction(caseId, 'finalize', payload);
export const returnReviewCase = (caseId, payload) => postReviewAction(caseId, 'return', payload);
export const fetchReviewerSummaries = (options) => request(`${API_BASE}/reviews/reviewers/summary`, options);

export const fetchModelMonitoring = (windowHours = 24, options) => request(`${API_BASE}/monitoring/model?window_hours=${windowHours}`, options);
export const fetchUsers = (options) => request(`${API_BASE}/auth/users`, options);
export const updateUserRole = (userId, role) => request(`${API_BASE}/auth/users/${userId}/role`, {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role }),
});
export const updateUserStatus = (userId, isActive) => request(`${API_BASE}/auth/users/${userId}/status`, {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_active: isActive }),
});

export const loginRequest = (payload) => request(`${API_BASE}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});
export const registerRequest = (payload) => request(`${API_BASE}/auth/register`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});
export const demoLoginRequest = (role) => request(`${API_BASE}/auth/demo`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ role }),
});
export const fetchCurrentUser = (options) => request(`${API_BASE}/auth/me`, options);

export async function pingBackend(options = {}) {
  try {
    await request('/openapi.json', { ...options, timeout: 4000 });
    return true;
  } catch {
    return false;
  }
}
