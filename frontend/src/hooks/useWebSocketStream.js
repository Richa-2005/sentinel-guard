import { useCallback, useEffect, useRef, useState } from 'react';

const MAX_STREAM_RECORDS = 200;
const MAX_RECONNECT_DELAY = 15000;
const HEARTBEAT_INTERVAL = 25000;

function buildWebSocketUrl() {
  const configuredUrl = import.meta.env.VITE_WS_URL;
  if (configuredUrl) return configuredUrl;
  const path = import.meta.env.VITE_WS_PATH || '/ws/live-feed';
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path.startsWith('/') ? path : `/${path}`}`;
}

function normalizeEvent(rawMessage) {
  const event = JSON.parse(rawMessage);
  if (!event || typeof event !== 'object' || typeof event.type !== 'string') return null;
  return { type: event.type, data: event.data && typeof event.data === 'object' ? event.data : {} };
}

export default function useWebSocketStream({ onTransaction, onAuditEvent, onReconnect } = {}) {
  const [liveStream, setLiveStream] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [lastEventAt, setLastEventAt] = useState(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [streamError, setStreamError] = useState('');
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const heartbeatRef = useRef(null);
  const mountedRef = useRef(false);
  const allowReconnectRef = useRef(true);
  const hasConnectedRef = useRef(false);
  const attemptRef = useRef(0);
  const callbacksRef = useRef({ onTransaction, onAuditEvent, onReconnect });

  useEffect(() => {
    callbacksRef.current = { onTransaction, onAuditEvent, onReconnect };
  }, [onTransaction, onAuditEvent, onReconnect]);

  const clearTimers = useCallback(() => {
    window.clearTimeout(reconnectTimerRef.current);
    window.clearInterval(heartbeatRef.current);
  }, []);

  const disconnect = useCallback(() => {
    allowReconnectRef.current = false;
    clearTimers();
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.close(1000, 'Client disconnect');
    } else if (socket && socket.readyState >= WebSocket.CLOSING) {
      socketRef.current = null;
    }
    if (mountedRef.current) setConnectionStatus('offline');
  }, [clearTimers]);

  const connect = useCallback(() => {
    if (!mountedRef.current || typeof WebSocket === 'undefined') return;
    allowReconnectRef.current = true;
    const current = socketRef.current;
    if (current && (current.readyState === WebSocket.OPEN || current.readyState === WebSocket.CONNECTING)) return;

    setConnectionStatus(hasConnectedRef.current ? 'reconnecting' : 'connecting');
    setStreamError('');
    const socket = new WebSocket(buildWebSocketUrl());
    socketRef.current = socket;

    socket.onopen = () => {
      if (!mountedRef.current || !allowReconnectRef.current) {
        socket.close(1000, 'Client inactive');
        return;
      }
      const isReconnect = hasConnectedRef.current;
      hasConnectedRef.current = true;
      attemptRef.current = 0;
      setReconnectAttempt(0);
      setConnectionStatus('connected');
      setStreamError('');
      window.clearInterval(heartbeatRef.current);
      heartbeatRef.current = window.setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send('ping');
      }, HEARTBEAT_INTERVAL);
      if (isReconnect) callbacksRef.current.onReconnect?.();
    };

    socket.onmessage = (message) => {
      if (!mountedRef.current || socketRef.current !== socket) return;
      try {
        const event = normalizeEvent(message.data);
        if (!event) return;
        setLastEventAt(new Date().toISOString());

        if (event.type === 'TRANSACTION_STREAM' && event.data.transaction_id) {
          setLiveStream((previous) => {
            const withoutDuplicate = previous.filter(
              (item) => item.transaction_id !== event.data.transaction_id
            );
            return [event.data, ...withoutDuplicate].slice(0, MAX_STREAM_RECORDS);
          });
          callbacksRef.current.onTransaction?.(event.data);
          return;
        }

        if (
          event.type === 'AUDIT_COMPLETE'
          || event.type === 'AUDIT_FAILED'
          || event.type === 'AUDIT_RETRY_SCHEDULED'
        ) {
          callbacksRef.current.onAuditEvent?.({
            ...event.data,
            transaction_id: event.data.transaction_id || event.data.id,
            status: event.type === 'AUDIT_FAILED'
              ? 'failed'
              : event.type === 'AUDIT_RETRY_SCHEDULED'
                ? 'processing'
                : event.data.status || 'complete',
          });
        }
      } catch {
        setStreamError('A malformed live event was ignored.');
      }
    };

    socket.onerror = () => {
      if (!mountedRef.current || socketRef.current !== socket) return;
      setStreamError('The live channel encountered a connection error.');
    };

    socket.onclose = () => {
      window.clearInterval(heartbeatRef.current);
      const isCurrentSocket = socketRef.current === socket;
      if (isCurrentSocket) socketRef.current = null;
      if (!isCurrentSocket) return;
      if (!mountedRef.current || !allowReconnectRef.current) return;

      attemptRef.current += 1;
      setReconnectAttempt(attemptRef.current);
      setConnectionStatus('reconnecting');
      const baseDelay = Math.min(500 * 2 ** (attemptRef.current - 1), MAX_RECONNECT_DELAY);
      const jitter = Math.floor(Math.random() * 250);
      reconnectTimerRef.current = window.setTimeout(connect, baseDelay + jitter);
    };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      allowReconnectRef.current = false;
      clearTimers();
      const socket = socketRef.current;
      if (socket?.readyState === WebSocket.OPEN) {
        socket.close(1000, 'Application unmounted');
      } else if (socket && socket.readyState >= WebSocket.CLOSING) {
        socketRef.current = null;
      }
      // A CONNECTING socket is intentionally not closed mid-handshake. If this
      // is a real unmount, onopen closes it; Strict Mode's remount reuses it.
    };
  }, [connect, clearTimers]);

  return {
    liveStream,
    connectionStatus,
    lastEventAt,
    reconnectAttempt,
    streamError,
    connect,
    disconnect,
  };
}

export { buildWebSocketUrl, normalizeEvent };
