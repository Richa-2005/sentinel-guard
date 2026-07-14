export default function PageSkeleton() {
  return <div className="page-skeleton" aria-label="Loading workspace"><div className="skeleton skeleton--title" /><div className="metric-grid">{Array.from({ length: 4 }, (_, i) => <div className="skeleton skeleton--metric" key={i} />)}</div><div className="skeleton skeleton--panel" /></div>;
}
