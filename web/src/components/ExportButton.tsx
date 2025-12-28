import { useState } from 'react';

export interface ExportButtonProps {
  onExport: () => Promise<void>;
  label?: string;
  disabled?: boolean;
  className?: string;
}

// SVG Download Icon Component
function DownloadIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

export interface ExportButtonProps {
  onExport: () => Promise<void>;
  label?: string;
  disabled?: boolean;
  className?: string;
}

export function ExportButton({
  onExport,
  label = 'Export CSV',
  disabled = false,
  className = '',
}: ExportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);

    try {
      await onExport();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Export failed';
      setError(message);
      console.error('Export error:', err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="inline-flex flex-col">
      <button
        onClick={handleExport}
        disabled={disabled || isExporting}
        className={`
          inline-flex items-center gap-2 px-4 py-2
          bg-blue-600 text-white rounded-md
          hover:bg-blue-700 active:bg-blue-800
          disabled:bg-gray-400 disabled:cursor-not-allowed
          transition-colors duration-150
          ${className}
        `}
        aria-label={label}
      >
        <DownloadIcon className={`w-4 h-4 ${isExporting ? 'animate-bounce' : ''}`} />
        <span>{isExporting ? 'Exporting...' : label}</span>
      </button>

      {error && (
        <div className="mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </div>
      )}
    </div>
  );
}
