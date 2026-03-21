import { useEffect, useState } from 'react';
import { useSpecPanelStore } from '../../stores/specPanelStore';
import { specs } from '../../api/endpoints';
import { SpecContent } from './SpecContent';
import { LoadingSpinner } from '../ui/LoadingSpinner';

export function SpecPanel() {
  const { isOpen, activeRef, owner, repo, prNumber, cachedContent, close, cacheContent } =
    useSpecPanelStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !activeRef) return;

    const path = activeRef.spec_file;
    if (cachedContent.has(path)) return;

    setLoading(true);
    setError(null);
    specs
      .content(owner, repo, prNumber, path)
      .then((content) => cacheContent(path, content))
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [isOpen, activeRef, owner, repo, prNumber, cachedContent, cacheContent]);

  if (!isOpen || !activeRef) return null;

  const content = cachedContent.get(activeRef.spec_file);

  return (
    <div className="w-96 border-l border-gray-200 bg-white flex flex-col ml-4 flex-shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="min-w-0">
          <div className="text-sm font-medium text-gray-900 truncate">{activeRef.heading}</div>
          <div className="text-xs text-gray-500 truncate">{activeRef.spec_file}</div>
        </div>
        <button
          onClick={close}
          className="text-gray-400 hover:text-gray-600 ml-2 cursor-pointer bg-transparent border-0 text-lg"
        >
          &times;
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {loading && <LoadingSpinner />}
        {error && <p className="text-red-600 text-sm">{error}</p>}
        {content && <SpecContent content={content.content} heading={activeRef.heading} />}
      </div>
    </div>
  );
}
