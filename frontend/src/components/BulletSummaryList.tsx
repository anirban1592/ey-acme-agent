import type { BulletSummaryResponse } from '../schemas/agentResponses';

export function BulletSummaryList({ data }: { data: BulletSummaryResponse }) {
  return (
    <div>
      <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{data.heading}</div>
      <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
        {data.points.map((point, i) => (
          <li key={i} style={{ fontSize: '0.9rem' }}>
            {point}
          </li>
        ))}
      </ul>
    </div>
  );
}
