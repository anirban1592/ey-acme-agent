import type { ErrorResponse } from '../schemas/agentResponses';

export function ErrorBanner({ data }: { data: ErrorResponse }) {
  return (
    <div
      style={{
        border: '1px solid #f5c2c2',
        background: '#ffe0e0',
        borderRadius: 6,
        padding: '0.5rem 0.75rem',
        color: '#8a1f1f',
        fontSize: '0.9rem',
      }}
    >
      <strong>Error ({data.code}):</strong> {data.message}
    </div>
  );
}
