import { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

type Props = {
	context: Record<string, unknown> | null;
	searchTerm?: string;
};

export function ContextViewer({ context, searchTerm }: Props) {
	const [isExpanded, setIsExpanded] = useState(false);

	if (!context || Object.keys(context).length === 0) {
		return null;
	}

	const hasExcText = 'exc_text' in context && typeof context.exc_text === 'string';
	const hasAction = 'action' in context;
	const hasExcInfo = 'exc_info' in context;

	// Highlight search term in text
	const highlightText = (text: string, term?: string): string => {
		if (!term || !text) return text;
		const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
		return text.replace(regex, '<mark class="bg-yellow-500/30 text-yellow-200">$1</mark>');
	};

	// Check if search term matches any context field
	const hasMatch = searchTerm
		? Object.values(context).some((value) =>
				String(value).toLowerCase().includes(searchTerm.toLowerCase())
		  )
		: false;

	return (
		<div className="mt-2 space-y-2">
			<button
				onClick={() => setIsExpanded(!isExpanded)}
				className={`text-xs transition-colors ${
					hasMatch && searchTerm
						? 'text-yellow-400 hover:text-yellow-300 font-semibold'
						: 'text-blue-400 hover:text-blue-300'
				}`}
				type="button"
			>
				{isExpanded ? '▼ Hide Context' : '▶ Show Context'}
				{hasMatch && searchTerm && ' (match)'}
			</button>

			{isExpanded && (
				<div className="bg-[#0f172a] border border-[#1f2937] rounded p-3 space-y-2">
					{hasAction && (
						<div className="flex items-center gap-2">
							<span className="text-xs text-[var(--muted)]">Action:</span>
							<span className="px-2 py-1 bg-blue-500/20 text-blue-300 rounded text-xs">
								{String(context.action)}
							</span>
						</div>
					)}

					{hasExcInfo && (
						<div className="flex items-center gap-2">
							<span className="text-xs text-red-400">⚠ Exception Info Present</span>
						</div>
					)}

					{hasExcText && (
						<div>
							<div className="text-xs text-red-400 mb-1 font-semibold">Stack Trace:</div>
							{searchTerm ? (
								<div
									className="bg-[#0a0e1a] border border-[#1f2937] rounded p-2 text-xs font-mono whitespace-pre-wrap"
									dangerouslySetInnerHTML={{
										__html: highlightText(String(context.exc_text), searchTerm),
									}}
								/>
							) : (
								<SyntaxHighlighter
									language="text"
									style={vscDarkPlus}
									customStyle={{
										margin: 0,
										padding: '0.5rem',
										fontSize: '0.75rem',
										borderRadius: '0.25rem',
										background: '#0a0e1a',
									}}
								>
									{String(context.exc_text)}
								</SyntaxHighlighter>
							)}
						</div>
					)}

					<div>
						<div className="text-xs text-[var(--muted)] mb-1">Full Context:</div>
						<SyntaxHighlighter
							language="json"
							style={vscDarkPlus}
							customStyle={{
								margin: 0,
								padding: '0.5rem',
								fontSize: '0.75rem',
								borderRadius: '0.25rem',
								background: '#0a0e1a',
							}}
						>
							{JSON.stringify(context, null, 2)}
						</SyntaxHighlighter>
					</div>
				</div>
			)}
		</div>
	);
}
