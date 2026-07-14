import { useCallback, useEffect, useRef, useState } from 'react';

const SAFE_CARDS = ['sql_card_01', 'sql_card_02', 'card_alpha_42'];
const THREAT_CARDS = ['card_token_999', 'attack_card_330', 'attack_card_964', 'stolen_card_signature_02'];
const SAFE_DEVICES = ['dev_mac_001', 'dev_android_88', 'dev_ios_12'];
const THREAT_DEVICES = ['malicious_device_ring_01', 'dev_mac_001'];

const randomItem = (list) => list[Math.floor(Math.random() * list.length)];

export default function useTrafficSimulator(merchants, onTransaction, backendOnline) {
  const [status, setStatus] = useState('stopped');
  const timerRef = useRef(null);
  const runningRef = useRef(false);
  const callbackRef = useRef(onTransaction);
  callbackRef.current = onTransaction;

  const randomPayload = useCallback(() => {
    const merchantIds = Object.keys(merchants);
    const threat = Math.random() > 0.75;
    return {
      amount_paise: threat ? Math.floor(Math.random() * 500000) + 260000 : Math.floor(Math.random() * 14500) + 500,
      card_id: randomItem(threat ? THREAT_CARDS : SAFE_CARDS),
      device_id: randomItem(threat ? THREAT_DEVICES : SAFE_DEVICES),
      merchant_id: merchantIds.length ? randomItem(merchantIds) : threat ? '7995' : '5411',
    };
  }, [merchants]);

  const stop = useCallback(() => {
    runningRef.current = false;
    window.clearTimeout(timerRef.current);
    setStatus('stopped');
  }, []);

  const runNext = useCallback(async () => {
    if (!runningRef.current) return;
    if (!backendOnline) {
      setStatus('offline');
      timerRef.current = window.setTimeout(runNext, 1500);
      return;
    }
    setStatus('running');
    await callbackRef.current(randomPayload(), { automated: true });
    if (!runningRef.current) return;
    setStatus('waiting');
    timerRef.current = window.setTimeout(runNext, 500);
  }, [backendOnline, randomPayload]);

  const start = useCallback(() => {
    if (runningRef.current) return;
    runningRef.current = true;
    runNext();
  }, [runNext]);

  useEffect(() => () => stop(), [stop]);
  useEffect(() => {
    if (runningRef.current && backendOnline && status === 'offline') runNext();
  }, [backendOnline, status, runNext]);

  return { status, start, stop, randomPayload };
}
