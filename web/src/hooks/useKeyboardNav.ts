import { useEffect, useCallback, useState } from 'react';

interface KeyboardNavOptions {
  fileCount: number;
  annotationCount: number;
  onToggleTheme: () => void;
  onCloseModal: () => void;
  onToggleFileTree?: () => void;
  walkthroughActive?: boolean;
  onWalkthroughNext?: () => void;
  onWalkthroughPrev?: () => void;
  onWalkthroughExit?: () => void;
}

export function useKeyboardNav({ fileCount, annotationCount, onToggleTheme, onCloseModal, onToggleFileTree, walkthroughActive, onWalkthroughNext, onWalkthroughPrev, onWalkthroughExit }: KeyboardNavOptions) {
  const [fileIndex, setFileIndex] = useState(-1);
  const [annIndex, setAnnIndex] = useState(-1);
  const [showHelp, setShowHelp] = useState(false);

  const scrollToFile = useCallback((idx: number) => {
    const el = document.querySelector(`[data-file-index="${idx}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Set focus indicator
      document.querySelectorAll('[data-file-focused]').forEach((e) => e.removeAttribute('data-file-focused'));
      el.setAttribute('data-file-focused', 'true');
    }
  }, []);

  const scrollToAnnotation = useCallback((idx: number) => {
    const els = document.querySelectorAll('[data-annotation-id]');
    const el = els[idx];
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, []);

  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      switch (e.key) {
        case 'j': {
          e.preventDefault();
          const next = Math.min(fileIndex + 1, fileCount - 1);
          setFileIndex(next);
          scrollToFile(next);
          break;
        }
        case 'k': {
          e.preventDefault();
          const prev = Math.max(fileIndex - 1, 0);
          setFileIndex(prev);
          scrollToFile(prev);
          break;
        }
        case 'n': {
          e.preventDefault();
          const next = Math.min(annIndex + 1, annotationCount - 1);
          setAnnIndex(next);
          scrollToAnnotation(next);
          break;
        }
        case 'p': {
          e.preventDefault();
          const prev = Math.max(annIndex - 1, 0);
          setAnnIndex(prev);
          scrollToAnnotation(prev);
          break;
        }
        case 'o': {
          if (fileIndex >= 0) {
            const fileEl = document.querySelector(`[data-file-index="${fileIndex}"]`);
            const btn = fileEl?.querySelector('button');
            btn?.click();
          }
          break;
        }
        case 'b': {
          onToggleFileTree?.();
          break;
        }
        case 't': {
          onToggleTheme();
          break;
        }
        case '?': {
          e.preventDefault();
          setShowHelp((h) => !h);
          break;
        }
        case ']':
        case 'ArrowRight': {
          if (walkthroughActive) {
            e.preventDefault();
            onWalkthroughNext?.();
          }
          break;
        }
        case '[':
        case 'ArrowLeft': {
          if (walkthroughActive) {
            e.preventDefault();
            onWalkthroughPrev?.();
          }
          break;
        }
        case 'Escape': {
          if (walkthroughActive) {
            onWalkthroughExit?.();
          }
          setShowHelp(false);
          onCloseModal();
          break;
        }
      }
    },
    [fileIndex, annIndex, fileCount, annotationCount, scrollToFile, scrollToAnnotation, onToggleTheme, onCloseModal, onToggleFileTree, walkthroughActive, onWalkthroughNext, onWalkthroughPrev, onWalkthroughExit],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [handleKey]);

  return { fileIndex, annIndex, showHelp, setShowHelp };
}
