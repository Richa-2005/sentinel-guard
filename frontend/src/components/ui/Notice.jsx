import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

const icons = { success: CheckCircle2, warning: AlertCircle, info: Info, danger: AlertCircle };

export default function Notice({ notice, onClose }) {
  const Icon = icons[notice.tone] || Info;
  return <aside className={`toast toast--${notice.tone || 'info'}`} role="status"><Icon size={18} /><div><strong>{notice.title}</strong><p>{notice.message}</p></div><button className="icon-button" onClick={onClose} aria-label="Dismiss notification"><X size={15} /></button></aside>;
}
