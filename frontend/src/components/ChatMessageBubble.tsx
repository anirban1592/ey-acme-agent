import type { ChatMessageResponse } from '../schemas/agentResponses';

export function ChatMessageBubble({ data }: { data: ChatMessageResponse }) {
  return <span style={{ whiteSpace: 'pre-wrap' }}>{data.message}</span>;
}
