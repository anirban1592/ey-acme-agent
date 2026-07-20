import { useEffect, useState } from 'react';

const PHRASES = ['Fetching…', 'Hold tight…', 'Cooking…', 'Almost there…'];
const CYCLE_MS = 1300;

export function WaitingIndicator() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % PHRASES.length);
    }, CYCLE_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="waiting-indicator">
      <span className="status-dot status-dot--signal" />
      <span>{PHRASES[index]}</span>
    </div>
  );
}
