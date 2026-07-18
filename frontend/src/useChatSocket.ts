import { useCallback, useEffect, useRef, useState } from 'react';

export type ChatMessage = {
  role: 'user' | 'agent' | 'system';
  text: string;
};

export type ConnectionState = 'connecting' | 'open' | 'closed';

export function useChatSocket(token: string | undefined) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting');
  const socketRef = useRef<WebSocket | null>(null);

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
    socket.send(JSON.stringify({ message: text }));
  }, []);

  return { messages, connectionState, sendMessage };
}
