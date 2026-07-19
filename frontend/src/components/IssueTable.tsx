import type { IssueListResponse } from '../schemas/agentResponses';

export function IssueTable({ data }: { data: IssueListResponse }) {
  return (
    <div>
      <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Issues for {data.customer_name}</div>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.9rem' }}>
        <thead>
          <tr>
            {['ID', 'Title', 'Status', 'Updated'].map((h) => (
              <th
                key={h}
                style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: '0.25rem 0.5rem' }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.issues.map((issue) => (
            <tr key={issue.id}>
              <td style={{ padding: '0.25rem 0.5rem', borderBottom: '1px solid #eee' }}>{issue.id}</td>
              <td style={{ padding: '0.25rem 0.5rem', borderBottom: '1px solid #eee' }}>{issue.title}</td>
              <td style={{ padding: '0.25rem 0.5rem', borderBottom: '1px solid #eee' }}>{issue.status}</td>
              <td style={{ padding: '0.25rem 0.5rem', borderBottom: '1px solid #eee' }}>
                {new Date(issue.updated_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
