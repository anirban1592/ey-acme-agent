import type { EscalationEmailResponse } from '../schemas/agentResponses';

export function EscalationEmailCard({ data }: { data: EscalationEmailResponse }) {
  return (
    <div
      style={{
        border: '1px solid var(--hairline)',
        borderRadius: 8,
        padding: '0.75rem',
        background: 'var(--panel-raised)',
        color: 'var(--paper)',
      }}
    >
      <div style={{ fontSize: '0.85rem', color: 'var(--fog)' }}>To: {data.to}</div>
      <div style={{ fontWeight: 600, margin: '0.25rem 0' }}>{data.subject}</div>
      <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>{data.body}</div>
    </div>
  );
}
