import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { Badge, EmptyState, Metric, PageGuide, Panel } from './Primitives';

describe('shared UI primitives', () => {
  it('render accessible semantic content', async () => {
    const { container } = render(<main><PageGuide title="Understand this workspace">Operational guidance.</PageGuide><Panel title="Activity ledger"><Metric label="Processed" value="24" detail="Loaded ledger" /><Badge tone="critical">Blocked</Badge><EmptyState title="No records" message="Evaluate a transaction to begin." /></Panel></main>);
    expect(screen.getByRole('heading', { name: 'Activity ledger' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Workspace guide' })).toBeInTheDocument();
    expect(screen.getByText('Blocked')).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
