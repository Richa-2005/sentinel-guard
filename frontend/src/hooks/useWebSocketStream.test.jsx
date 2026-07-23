import { StrictMode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import useWebSocketStream, { normalizeEvent } from './useWebSocketStream';

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    MockWebSocket.instances.push(this);
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  receive(event) {
    this.onmessage?.({ data: JSON.stringify(event) });
  }

  send = vi.fn();

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }
}

describe('useWebSocketStream', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('normalizes supported event envelopes', () => {
    expect(normalizeEvent(JSON.stringify({ type: 'AUDIT_COMPLETE', data: { id: 'tx-1' } })))
      .toEqual({ type: 'AUDIT_COMPLETE', data: { id: 'tx-1' } });
    expect(normalizeEvent(JSON.stringify({ data: {} }))).toBeNull();
  });

  it('reuses an in-flight handshake during the Strict Mode effect replay', () => {
    const wrapper = ({ children }) => <StrictMode>{children}</StrictMode>;
    const { result } = renderHook(() => useWebSocketStream({ token: 'test-token' }), { wrapper });

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].readyState).toBe(MockWebSocket.CONNECTING);

    act(() => MockWebSocket.instances[0].open());
    act(() => MockWebSocket.instances[0].receive({ type: 'authenticated' }));
    expect(result.current.connectionStatus).toBe('connected');
  });

  it('streams transactions and forwards correlated audit completion events', async () => {
    const onTransaction = vi.fn();
    const onAuditEvent = vi.fn();
    const { result } = renderHook(() => useWebSocketStream({ token: 'test-token', onTransaction, onAuditEvent }));
    const socket = MockWebSocket.instances[0];

    act(() => socket.open());
    expect(socket.send).toHaveBeenCalledWith(JSON.stringify({ type: 'authenticate', token: 'test-token' }));
    act(() => socket.receive({ type: 'authenticated' }));
    await waitFor(() => expect(result.current.connectionStatus).toBe('connected'));

    act(() => socket.receive({
      type: 'TRANSACTION_STREAM',
      data: { transaction_id: 'tx-1', card_id: 'card-1', is_blocked: true },
    }));
    expect(result.current.liveStream).toHaveLength(1);
    expect(onTransaction).toHaveBeenCalledWith(expect.objectContaining({ transaction_id: 'tx-1' }));

    act(() => socket.receive({ type: 'AUDIT_COMPLETE', data: { id: 'tx-1' } }));
    expect(onAuditEvent).toHaveBeenCalledWith(expect.objectContaining({
      transaction_id: 'tx-1',
      status: 'complete',
    }));

    act(() => socket.receive({
      type: 'AUDIT_RETRY_SCHEDULED',
      data: { transaction_id: 'tx-2', attempts: 1 },
    }));
    expect(onAuditEvent).toHaveBeenCalledWith(expect.objectContaining({
      transaction_id: 'tx-2',
      status: 'processing',
      attempts: 1,
    }));
  });

  it('ignores malformed messages without terminating the channel', () => {
    const { result } = renderHook(() => useWebSocketStream({ token: 'test-token' }));
    const socket = MockWebSocket.instances[0];
    act(() => socket.open());
    act(() => socket.receive({ type: 'authenticated' }));
    act(() => socket.onmessage?.({ data: '{broken-json' }));
    expect(result.current.connectionStatus).toBe('connected');
    expect(result.current.streamError).toMatch(/malformed/i);
  });
});
