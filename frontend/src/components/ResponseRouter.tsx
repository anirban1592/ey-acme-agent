import type { AgentResponse } from '../schemas/agentResponses';
import { BulletSummaryList } from './BulletSummaryList';
import { ChatMessageBubble } from './ChatMessageBubble';
import { CustomerProfileTable } from './CustomerProfileTable';
import { ErrorBanner } from './ErrorBanner';
import { EscalationEmailCard } from './EscalationEmailCard';
import { IssueTable } from './IssueTable';

function assertNever(x: never): never {
  throw new Error(`Unhandled response type: ${JSON.stringify(x)}`);
}

export function ResponseRouter({ response }: { response: AgentResponse }) {
  switch (response.type) {
    case 'issue_list':
      return <IssueTable data={response} />;
    case 'customer_profile':
      return <CustomerProfileTable data={response} />;
    case 'escalation_email':
      return <EscalationEmailCard data={response} />;
    case 'bullet_summary':
      return <BulletSummaryList data={response} />;
    case 'chat_message':
      return <ChatMessageBubble data={response} />;
    case 'error':
      return <ErrorBanner data={response} />;
    default:
      return assertNever(response);
  }
}
