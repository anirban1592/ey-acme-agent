import type { ConnectionState } from '../useChatSocket';

function dotClassFor(connectionState: ConnectionState): string {
  switch (connectionState) {
    case 'open':
      return 'status-dot status-dot--ok';
    case 'connecting':
      return 'status-dot status-dot--signal';
    case 'closed':
      return 'status-dot status-dot--danger';
  }
}

export function Header({
  username,
  connectionState,
  onLogout,
}: {
  username?: string;
  connectionState: ConnectionState;
  onLogout: () => void;
}) {
  return (
    <header className="header-bar">
      <h1 className="header-title">Acme Support Companion</h1>
      <div className="header-user">
        <div className="header-user-info">
          <span className={dotClassFor(connectionState)} />
          {username && <span className="header-username">{username}</span>}
        </div>
        <button type="button" className="btn btn-ghost" onClick={onLogout}>
          Log out
        </button>
      </div>
    </header>
  );
}
