import type { StoredThread } from '../conversationStore';

export function Sidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onNewChat,
}: {
  threads: StoredThread[];
  activeThreadId: string;
  onSelectThread: (id: string) => void;
  onNewChat: () => void;
}) {
  const sorted = [...threads].sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));

  return (
    <aside className="sidebar">
      <button type="button" className="btn btn-primary sidebar-new-chat-btn" onClick={onNewChat}>
        + New chat
      </button>
      <div className="sidebar-eyebrow">Conversations</div>
      <div className="sidebar-thread-list">
        {sorted.map((thread) => {
          const isActive = thread.id === activeThreadId;
          return (
            <button
              key={thread.id}
              type="button"
              className={`sidebar-thread-item${isActive ? ' sidebar-thread-item--active' : ''}`}
              onClick={() => onSelectThread(thread.id)}
            >
              <span className={`status-dot ${isActive ? 'status-dot--signal' : 'status-dot--idle'}`} />
              <span className="sidebar-thread-text">
                <div className="sidebar-thread-title">{thread.title}</div>
                <div className="sidebar-thread-meta">{new Date(thread.updatedAt).toLocaleString()}</div>
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
