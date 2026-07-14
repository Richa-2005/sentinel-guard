import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, evaluateTransaction, fetchTransactions } from './client';

afterEach(() => vi.restoreAllMocks());

describe('API client', () => {
  it('preserves the existing evaluation payload and response contract', async () => {
    const payload = { amount_paise: 1250, card_id: 'card_1', device_id: 'device_1', merchant_id: '5411' };
    const response = { is_blocked: false, ensemble_risk_score: 0.002, hydrated_metrics: {}, shap_payload: {}, status: 'evaluated' };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: async () => response });
    await expect(evaluateTransaction(payload)).resolves.toEqual(response);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(payload);
  });

  it('normalizes backend validation failures', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: 'Invalid transaction' }) });
    await expect(fetchTransactions()).rejects.toMatchObject({ name: 'ApiError', code: 'VALIDATION_ERROR', status: 422 });
  });

  it('normalizes connectivity failures', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('network down'));
    await expect(fetchTransactions()).rejects.toEqual(expect.objectContaining({ code: 'NETWORK_ERROR' }));
  });
});
