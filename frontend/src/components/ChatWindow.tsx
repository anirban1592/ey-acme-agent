import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useChatSocket, type ChatMessage, type ConnectionState } from '../useChatSocket';
import { ResponseRouter } from './ResponseRouter';
import { WaitingIndicator } from './WaitingIndicator';

export function ChatWindow({
  token,
  threadId,
  initialMessages,
  onTranscriptChange,
  onConnectionStateChange,
}: {
  token: string;
  threadId: string;
  initialMessages: ChatMessage[];
  onTranscriptChange: (threadId: string, messages: ChatMessage[]) => void;
  onConnectionStateChange: (connectionState: ConnectionState) => void;
}) {
  // Frozen once per mount — a fresh mount happens exactly when `threadId`
  // (the parent's `key`) changes, i.e. on thread switch / new chat.
  const [baseline] = useState(() => initialMessages);
  const { messages: liveMessages, connectionState, sendMessage } = useChatSocket(token);
  const [input, setInput] = useState('');

  const combined = useMemo(() => [...baseline, ...liveMessages], [baseline, liveMessages]);
  const isWaiting = combined.length > 0 && combined[combined.length - 1].role === 'user';

  useEffect(() => {
    onTranscriptChange(threadId, combined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, combined]);

  useEffect(() => {
    onConnectionStateChange(connectionState);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionState]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    sendMessage(text);
    setInput('');
  };

  const canSend = connectionState === 'open' && !isWaiting;

  return (
    <div className="chat-window">
      <div className="chat-transcript">
        {combined.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="chat-row chat-row--user">
              <span className="chat-bubble chat-bubble--user">{m.text}</span>
            </div>
          ) : (
            <div key={i} className="chat-row chat-row--agent">
              <div className={`chat-bubble chat-bubble--agent${m.response.type === 'error' ? ' chat-bubble--error' : ''}`}>
                <ResponseRouter response={m.response} />
              </div>
            </div>
          ),
        )}
        {isWaiting && (
          <div className="chat-row chat-row--agent">
            <WaitingIndicator />
          </div>
        )}
      </div>
      <form onSubmit={handleSubmit} className="chat-input-bar">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          className="chat-input"
          disabled={connectionState !== 'open'}
        />
        <button type="submit" className="btn btn-primary" disabled={!canSend}>
          Send
        </button>
      </form>
    </div>
  );
}
