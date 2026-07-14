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
    const response = await fetch(path, { ...options, signal: controller.signal });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(body?.detail || `Request failed with status ${response.status}`, {
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
export const fetchMerchants = (options) => request(`${API_BASE}/merchants`, options);

export async function pingBackend(options = {}) {
  try {
    await request('/openapi.json', { ...options, timeout: 4000 });
    return true;
  } catch {
    return false;
  }
}
