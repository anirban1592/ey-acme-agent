import React, { useEffect, useState } from 'react';
import Keycloak from 'keycloak-js';

// Keycloak configuration – matches the realm‑export.json
const keycloak = new Keycloak({
  url: 'http://localhost:8080',
  realm: 'assistant',
  clientId: 'frontend-spa',
});

export const App: React.FC = () => {
  const [claims, setClaims] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initialize Keycloak; "login-required" forces a redirect if not logged in
    keycloak
      .init({ onLoad: 'login-required', pkceMethod: 'S256' })
      .then((authenticated) => {
        if (!authenticated) {
          // Should never happen because login-required forces a login
          console.warn('User not authenticated');
          return;
        }
        // Once we have a token, call the backend /me endpoint
        fetch('http://localhost:8000/me', {
          headers: {
            Authorization: `Bearer ${keycloak.token}`,
          },
        })
          .then((res) => {
            if (!res.ok) throw new Error('Backend call failed');
            return res.json();
          })
          .then((data) => {
            setClaims(data);
          })
          .catch((err) => console.error(err))
          .finally(() => setLoading(false));
      })
      .catch((err) => console.error('Keycloak init error', err));
  }, []);

  if (loading) return <div>Loading…</div>;
  return (
    <div style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>🛡️ Authenticated!</h1>
      <pre style={{ background: '#f0f0f0', padding: '1rem' }}>{JSON.stringify(claims, null, 2)}</pre>
    </div>
  );
};
