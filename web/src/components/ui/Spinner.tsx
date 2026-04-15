import { useEffect, useState } from 'react';

const frames = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏';

export function Spinner({ interval = 80 }: { interval?: number }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % frames.length), interval);
    return () => clearInterval(id);
  }, [interval]);
  return <span aria-hidden="true">{frames[i]}</span>;
}
