import type { CustomerProfileResponse } from '../schemas/agentResponses';

export function CustomerProfileTable({ data }: { data: CustomerProfileResponse }) {
  const entries = Object.entries(data.fields);
  return (
    <div>
      <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>{data.customer_name} — Profile</div>
      {entries.length === 0 ? (
        <div style={{ color: '#666' }}>No profile found.</div>
      ) : (
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.9rem' }}>
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td style={{ padding: '0.25rem 0.5rem', borderBottom: '1px solid #eee', fontWeight: 500 }}>
                  {key.replace(/_/g, ' ')}
                </td>
                <td style={{ padding: '0.25rem 0.5rem', borderBottom: '1px solid #eee' }}>{value ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
