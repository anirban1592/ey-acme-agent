import React, { useEffect, useRef, useState } from 'react';
import Keycloak from 'keycloak-js';
import { Chat } from './Chat';

// Keycloak configuration – matches the realm‑export.json
const keycloak = new Keycloak({
  url: 'http://localhost:8080',
  realm: 'assistant',
  clientId: 'frontend-spa',
});

export const App: React.FC = () => {
  const [authenticated, setAuthenticated] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);
  const didInit = useRef(false);

  useEffect(() => {
    // Guard against React.StrictMode's double effect invocation in dev —
    // keycloak-js only supports calling init() once per instance; a second
    // call while the first is still processing the redirect's auth code
    // causes a login redirect loop.
    if (didInit.current) return;
    didInit.current = true;

    // Initialize Keycloak; "check-sso" runs the SSO check in a hidden iframe
    // instead of a full-page redirect, so it can't race/collide with the
    // top-level navigation the way "login-required" did. If there's no SSO
    // session, we fall back to an explicit keycloak.login() redirect.
    keycloak
      .init({
        onLoad: 'check-sso',
        pkceMethod: 'S256',
        silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
        checkLoginIframe: false,
      })
      .then((authenticated) => {
        if (!authenticated) {
          void keycloak.login();
          return;
        }
        setAuthenticated(true);
        setAuthLoading(false);
      })
      .catch((err) => console.error('Keycloak init error', err));
  }, []);

  if (authLoading) return <div>Loading…</div>;
  if (!authenticated) return <div>Redirecting to login…</div>;

  const username = keycloak.tokenParsed?.preferred_username as string | undefined;
  const handleLogout = () => keycloak.logout({ redirectUri: window.location.origin });

  // Keying by username forces a full remount (and thus a fresh, correctly
  // re-namespaced conversationStore bootstrap) if the logged-in user ever
  // changes without a full page navigation.
  return <Chat key={username ?? 'anonymous'} token={keycloak.token!} username={username} onLogout={handleLogout} />;
};
