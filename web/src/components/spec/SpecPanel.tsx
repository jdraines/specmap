import { useEffect, useState } from 'react';
import { useSpecPanelStore } from '../../stores/specPanelStore';
import { specs } from '../../api/endpoints';
import { SpecContent } from './SpecContent';
import { LoadingSpinner } from '../ui/LoadingSpinner';

export function SpecPanel() {
  const { isModalOpen, modalRef, fullName, prNumber, cachedContent, closeModal, cacheContent } =
    useSpecPanelStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isModalOpen || !modalRef) return;

    const path = modalRef.spec_file;
    if (cachedContent.has(path)) return;

    setLoading(true);
    setError(null);
    specs
      .content(fullName, prNumber, path)
      .then((content) => cacheContent(path, content))
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [isModalOpen, modalRef, fullName, prNumber, cachedContent, cacheContent]);

  if (!isModalOpen || !modalRef) return null;

  const content = cachedContent.get(modalRef.spec_file);

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-[9990]" onClick={closeModal} />
      {/* Drawer */}
      <div className="fixed top-0 right-0 h-screen w-[480px] max-w-[90vw] bg-[var(--surface-1)] border-l border-[var(--border)] z-[9991] flex flex-col shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-[var(--text-primary)] truncate">
              {modalRef.heading}
            </div>
            <div className="text-xs text-[var(--text-muted)] truncate">{modalRef.spec_file}</div>
          </div>
          <button
            onClick={closeModal}
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] ml-2 cursor-pointer bg-transparent border-0 text-sm"
          >
            [x]
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading && <LoadingSpinner />}
          {error && <p className="text-[var(--error-text)] text-sm">{error}</p>}
          {content && <SpecContent content={content.content} heading={modalRef.heading} />}
        </div>
      </div>
    </>
  );
}
