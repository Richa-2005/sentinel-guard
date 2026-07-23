import { AlertCircle, CircleHelp, Inbox } from 'lucide-react';

export function Panel({ title, eyebrow, action, className = '', children, ...props }) {
  return <section className={`panel ${className}`} {...props}>{(title || action) && <header className="panel-header"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}{title && <h2>{title}</h2>}</div>{action}</header>}<div className="panel-body">{children}</div></section>;
}

export function Badge({ tone = 'neutral', children }) {
  return <span className={`badge badge--${tone}`}><span aria-hidden="true" />{children}</span>;
}

export function EmptyState({ title, message, error = false, action }) {
  const Icon = error ? AlertCircle : Inbox;
  return <div className="empty-state"><Icon size={24} /><h3>{title}</h3><p>{message}</p>{action}</div>;
}

export function Metric({ label, value, detail, tone = 'neutral' }) {
  return <div className={`metric metric--${tone}`}><div><span>{label}</span>{detail && <small>{detail}</small>}</div><strong>{value}</strong></div>;
}

export function PageGuide({ title, children }) {
  return (
    <div className="page-guide">
      <button type="button" className="page-guide-trigger" aria-describedby="page-guide-content">
        <CircleHelp size={16} />
        <span>Workspace guide</span>
      </button>
      <div className="page-guide-popover" id="page-guide-content" role="tooltip">
        <span className="eyebrow">Know this workspace</span>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}
