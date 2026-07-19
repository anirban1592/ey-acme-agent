import { useCallback, useEffect, useRef, useState } from 'react';

export type ChatMessage = {
  role: 'user' | 'agent' | 'system';
  text: string;
};

export type ConnectionState = 'connecting' | 'open' | 'closed';

const THREAD_ID_COOKIE = 'chat_thread_id';

function getCookie(name: string): string | undefined {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : undefined;
}

function setCookie(name: string, value: string): void {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${60 * 60 * 24 * 30}`;
}

export function useChatSocket(token: string | undefined) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting');
  const socketRef = useRef<WebSocket | null>(null);
  const threadIdRef = useRef<string | undefined>(getCookie(THREAD_ID_COOKIE));

  useEffect(() => {
    if (!token) return;

    setConnectionState('connecting');
    const socket = new WebSocket(`ws://localhost:8000/ws/chat?token=${encodeURIComponent(token)}`);
    socketRef.current = socket;

    socket.onopen = () => setConnectionState('open');
    socket.onclose = () => setConnectionState('closed');
    socket.onerror = () => setConnectionState('closed');
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.reply) {
        if (data.thread_id) {
          threadIdRef.current = data.thread_id;
          setCookie(THREAD_ID_COOKIE, data.thread_id);
        }
        setMessages((prev) => [...prev, { role: 'agent', text: data.reply }]);
      } else if (data.error) {
        setMessages((prev) => [...prev, { role: 'system', text: `Error: ${data.error}` }]);
      }
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [token]);

  const sendMessage = useCallback((text: string) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    setMessages((prev) => [...prev, { role: 'user', text }]);
    socket.send(JSON.stringify({ message: text, thread_id: threadIdRef.current }));
  }, []);

  return { messages, connectionState, sendMessage };
}
