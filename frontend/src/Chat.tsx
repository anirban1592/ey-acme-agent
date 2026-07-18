import React, { useState } from 'react';
import { useChatSocket } from './useChatSocket';

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
        {messages.map((m, i) => (
          <div key={i} style={{ textAlign: m.role === 'user' ? 'right' : 'left', margin: '0.5rem 0' }}>
            <span
              style={{
                display: 'inline-block',
                padding: '0.5rem 0.75rem',
                borderRadius: 12,
                background: m.role === 'user' ? '#0b93f6' : m.role === 'agent' ? '#e5e5ea' : '#ffe0e0',
                color: m.role === 'user' ? '#fff' : '#000',
                maxWidth: '80%',
              }}
            >
              {m.text}
            </span>
          </div>
        ))}
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
