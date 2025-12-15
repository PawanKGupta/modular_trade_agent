import { useState } from 'react';
import type { ServiceLogEntry } from '@/api/logs';

type Props = {
	log: ServiceLogEntry;
};

export function LogIdCell({ log }: Props) {
	const [copied, setCopied] = useState(false);
	const logId = String(log.id);

	// Parse file:line format if applicable
	const isFileLineFormat = logId.includes(':');
	const [fileName, lineNumber] = isFileLineFormat ? logId.split(':') : [null, null];

	const handleCopy = async () => {
		try {
			await navigator.clipboard.writeText(logId);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		} catch (err) {
			console.error('Failed to copy:', err);
		}
	};

	return (
		<div className="group relative">
			<button
				type="button"
				onClick={handleCopy}
				className="text-xs font-mono text-[var(--muted)] hover:text-blue-400 transition-colors cursor-pointer"
				title="Click to copy log ID"
			>
				{isFileLineFormat ? (
					<>
						<span className="text-blue-400">{fileName}</span>
						<span className="text-[var(--muted)]">:</span>
						<span className="text-green-400">{lineNumber}</span>
					</>
				) : (
					logId
				)}
			</button>
			{copied && (
				<div className="absolute left-0 top-6 z-20 bg-green-600 text-white text-xs px-2 py-1 rounded shadow-lg whitespace-nowrap">
					Copied!
				</div>
			)}
			{isFileLineFormat && (
				<div className="absolute left-0 top-6 z-10 bg-[#0f172a] border border-[#1f2937] text-xs px-2 py-1 rounded shadow-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
					<div>File: {fileName}</div>
					<div>Line: {lineNumber}</div>
				</div>
			)}
		</div>
	);
}
