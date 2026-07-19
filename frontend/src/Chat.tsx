import React, { useState } from 'react';
import { useChatSocket } from './useChatSocket';
import { ResponseRouter } from './components/ResponseRouter';

export const Chat: React.FC<{ token: string }> = ({ token }) => {
  const { messages, connectionState, sendMessage } = useChatSocket(token);
  const [input, setInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    sendMessage(text);
    setInput('');
  };

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '2rem', maxWidth: 600, margin: '0 auto' }}>
      <h1>Customer Issue &amp; Account Assistant</h1>
      <p style={{ color: '#666' }}>Connection: {connectionState}</p>
      <div
        style={{
          border: '1px solid #ccc',
          borderRadius: 8,
          padding: '1rem',
          height: 400,
          overflowY: 'auto',
          marginBottom: '1rem',
        }}
      >
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} style={{ textAlign: 'right', margin: '0.5rem 0' }}>
              <span
                style={{
                  display: 'inline-block',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 12,
                  background: '#0b93f6',
                  color: '#fff',
                  maxWidth: '80%',
                }}
              >
                {m.text}
              </span>
            </div>
          ) : (
            <div key={i} style={{ textAlign: 'left', margin: '0.5rem 0' }}>
              <div
                style={{
                  display: 'inline-block',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 12,
                  background: m.response.type === 'error' ? 'transparent' : '#e5e5ea',
                  color: '#000',
                  maxWidth: '100%',
                }}
              >
                <ResponseRouter response={m.response} />
              </div>
            </div>
          ),
        )}
      </div>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          style={{ flex: 1, padding: '0.5rem' }}
          disabled={connectionState !== 'open'}
        />
        <button type="submit" disabled={connectionState !== 'open'}>
          Send
        </button>
      </form>
    </div>
  );
};
