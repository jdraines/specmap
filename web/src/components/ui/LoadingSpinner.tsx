import { useState, useEffect } from 'react';

const FRAMES = ['|', '/', '-', '\\'];

export function LoadingSpinner() {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setFrame((f) => (f + 1) % FRAMES.length), 120);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center justify-center p-8">
      <span className="text-lg text-[var(--text-muted)]">{FRAMES[frame]}</span>
    </div>
  );
}
