import { useRef, useState } from 'react';
import type { ChatMessage, ConnectionState } from './useChatSocket';
import {
  bootstrapThreads,
  createThread,
  saveThreads,
  setActiveThreadCookie,
  upsertThreadMessages,
  type StoredThread,
} from './conversationStore';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';

export function Chat({
  token,
  username,
  onLogout,
}: {
  token: string;
  username?: string;
  onLogout: () => void;
}) {
  // Namespaces every localStorage read/write to the logged-in user, so two
  // accounts sharing a browser never see each other's threads.
  const userKey = username ?? 'anonymous';

  const bootstrapRef = useRef<{ threads: StoredThread[]; activeThreadId: string } | null>(null);
  if (bootstrapRef.current === null) {
    bootstrapRef.current = bootstrapThreads(userKey, username ?? 'there');
  }

  const [threads, setThreads] = useState<StoredThread[]>(bootstrapRef.current.threads);
  const [activeThreadId, setActiveThreadId] = useState<string>(bootstrapRef.current.activeThreadId);
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting');

  function handleNewChat() {
    const thread = createThread(username ?? 'there');
    setActiveThreadCookie(thread.id);
    setThreads((prev) => saveThreads(userKey, [thread, ...prev]));
    setActiveThreadId(thread.id);
  }

  function handleSelectThread(id: string) {
    if (id === activeThreadId) return;
    setActiveThreadCookie(id);
    setActiveThreadId(id);
  }

  function handleTranscriptChange(threadId: string, messages: ChatMessage[]) {
    setThreads((prev) => saveThreads(userKey, upsertThreadMessages(prev, threadId, messages)));
  }

  const active = threads.find((t) => t.id === activeThreadId);

  return (
    <div className="app-shell">
      <Header username={username} connectionState={connectionState} onLogout={onLogout} />
      <div className="app-body">
        <Sidebar
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={handleSelectThread}
          onNewChat={handleNewChat}
        />
        <ChatWindow
          key={activeThreadId}
          token={token}
          threadId={activeThreadId}
          initialMessages={active?.messages ?? []}
          onTranscriptChange={handleTranscriptChange}
          onConnectionStateChange={setConnectionState}
        />
      </div>
    </div>
  );
}
