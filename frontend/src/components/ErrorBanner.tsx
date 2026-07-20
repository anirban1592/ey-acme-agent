import type { ErrorResponse } from '../schemas/agentResponses';

export function ErrorBanner({ data }: { data: ErrorResponse }) {
  return (
    <div
      style={{
        border: '1px solid var(--danger)',
        background: 'var(--danger-bg)',
        borderRadius: 6,
        padding: '0.5rem 0.75rem',
        color: 'var(--danger)',
        fontSize: '0.9rem',
      }}
    >
      <strong>Error ({data.code}):</strong> {data.message}
    </div>
  );
}
