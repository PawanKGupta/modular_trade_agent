interface TaskDetailsViewProps {
	details: Record<string, any>;
}

export function TaskDetailsView({ details }: TaskDetailsViewProps) {
	// Extract key fields for special formatting
	const {
		timeout_seconds,
		max_retries,
		return_code,
		success,
		stdout_tail,
		stderr_tail,
		analysis_summary,
		error_type,
		error_message,
		exception,
		...remainingFields
	} = details;

	// Automatically extract task-specific metrics (counts, placed, modified, etc.)
	const taskMetrics: Record<string, number> = {};
	const otherFields: Record<string, any> = {};

	Object.entries(remainingFields).forEach(([key, value]) => {
		// Check if it's a numeric metric field (count, placed, modified, closed, etc.)
		if (
			typeof value === 'number' &&
			(key.endsWith('_count') ||
			 key.endsWith('_placed') ||
			 key.endsWith('_modified') ||
			 key.endsWith('_closed') ||
			 key.endsWith('_updated') ||
			 key.endsWith('_deleted') ||
			 key.endsWith('_processed') ||
			 key.endsWith('_inserted') ||
			 key.endsWith('_skipped') ||
			 key.endsWith('_failed') ||
			 key.endsWith('_retried'))
		) {
			taskMetrics[key] = value;
		} else {
			otherFields[key] = value;
		}
	});

	// Format and syntax highlight log lines with 200 char truncation
	const formatLogLine = (line: string, index: number) => {
		const trimmedLine = line.trim();
		if (!trimmedLine) return null;

		const maxLength = 200;
		const isTruncated = trimmedLine.length > maxLength;
		const displayLine = isTruncated ? trimmedLine.substring(0, maxLength) : trimmedLine;

		// Determine color based on log level
		let colorClass = 'text-[var(--muted)]';
		if (trimmedLine.includes(' - ERROR - ')) {
			colorClass = 'text-red-400';
		} else if (trimmedLine.includes(' - WARNING - ') || trimmedLine.includes(' - WARN - ')) {
			colorClass = 'text-yellow-400';
		} else if (trimmedLine.includes(' - INFO - ')) {
			colorClass = 'text-blue-300';
		} else if (trimmedLine.includes(' - SUCCESS - ')) {
			colorClass = 'text-green-400';
		}

		if (isTruncated) {
			return (
				<details key={`line-${index}`} className="group cursor-pointer">
					<summary className={`${colorClass} list-none hover:opacity-80`}>
						{displayLine}
						<span className="text-[var(--muted)] ml-1 text-[10px]">... [+{trimmedLine.length - maxLength} chars - click to expand]</span>
					</summary>
					<div className={`${colorClass} mt-1 pl-4 border-l-2 border-[var(--muted)] break-all`}>
						{trimmedLine}
					</div>
				</details>
			);
		}

		return <div key={`line-${index}`} className={colorClass}>{displayLine}</div>;
	};

	const formatLogTail = (logTail: string | null | undefined) => {
		if (!logTail) return null;
		const lines = logTail.split('\n').filter(line => line.trim());
		const displayLines = lines.slice(-10); // Show only last 10 lines

		return (
			<div className="space-y-0.5">
				{lines.length > 10 && (
					<div className="text-[var(--muted)] italic text-[10px]">
						... ({lines.length - 10} earlier lines hidden)
					</div>
				)}
				{displayLines.map((line, idx) => formatLogLine(line, idx))}
			</div>
		);
	};

	return (
		<div className="mt-2 p-4 bg-[#0a0f16] border border-[#1e293b] rounded-lg text-xs text-[var(--text)] space-y-4 max-w-full">
			{/* Key Metrics - Compact Pills */}
			<div className="flex flex-wrap gap-2">
				{success !== undefined && (
					<div className={`px-3 py-1.5 rounded-full ${success ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
						<span className="text-[var(--muted)]">Status: </span>
						<span className={`font-semibold ${success ? 'text-green-400' : 'text-red-400'}`}>
							{success ? 'Success' : 'Failed'}
						</span>
					</div>
				)}
				{return_code !== undefined && (
					<div className={`px-3 py-1.5 rounded-full ${return_code === 0 ? 'bg-green-500/10 border border-green-500/30' : 'bg-yellow-500/10 border border-yellow-500/30'}`}>
						<span className="text-[var(--muted)]">Exit Code: </span>
						<span className={`font-semibold ${return_code === 0 ? 'text-green-400' : 'text-yellow-400'}`}>
							{return_code}
						</span>
					</div>
				)}
				{timeout_seconds !== undefined && (
					<div className="px-3 py-1.5 rounded-full bg-gray-500/10 border border-gray-500/30">
						<span className="text-[var(--muted)]">Timeout: </span>
						<span className="text-[var(--text)]">{timeout_seconds}s</span>
					</div>
				)}
				{max_retries !== undefined && (
					<div className="px-3 py-1.5 rounded-full bg-gray-500/10 border border-gray-500/30">
						<span className="text-[var(--muted)]">Max Retries: </span>
						<span className="text-[var(--text)]">{max_retries}</span>
					</div>
				)}
			</div>

			{/* Task Metrics (automatically extracted from any service) */}
			{Object.keys(taskMetrics).length > 0 && (
				<div className="bg-[#0f1720] border border-blue-500/30 rounded p-3">
					<div className="text-blue-400 font-semibold mb-3 flex items-center gap-2">
						<span>📊</span> Task Metrics
					</div>
					<div className="grid grid-cols-2 md:grid-cols-4 gap-3">
						{Object.entries(taskMetrics).map(([key, value]) => {
							// Determine color based on metric type
							let colorClass = 'text-blue-400';
							if (key.includes('sell') || key.includes('closed') || key.includes('deleted')) {
								colorClass = 'text-red-400';
							} else if (key.includes('buy') || key.includes('inserted') || key.includes('processed')) {
								colorClass = 'text-green-400';
							} else if (key.includes('modified') || key.includes('updated') || key.includes('retried')) {
								colorClass = 'text-yellow-400';
							} else if (key.includes('failed') || key.includes('error')) {
								colorClass = 'text-red-500';
							} else if (key.includes('skipped')) {
								colorClass = 'text-gray-400';
							}

							// Format the label (e.g., "sell_orders_placed" -> "Sell Orders Placed")
							const label = key
								.split('_')
								.map(word => word.charAt(0).toUpperCase() + word.slice(1))
								.join(' ');

							return (
								<div key={key} className="text-center">
									<div className={`text-2xl font-bold ${colorClass}`}>{value}</div>
									<div className="text-[10px] text-[var(--muted)] uppercase tracking-wide mt-1">{label}</div>
								</div>
							);
						})}
					</div>
				</div>
			)}

			{/* Analysis Summary - Compact Grid */}
			{analysis_summary && (
				<div className="bg-[#0f1720] border border-[#1e293b] rounded p-3">
					<div className="text-[var(--text)] font-semibold mb-2 flex items-center gap-2">
						<span>📊</span> Analysis Summary
					</div>
					<div className="grid grid-cols-4 gap-3">
						{Object.entries(analysis_summary).map(([key, value]) => (
							<div key={key} className="text-center">
								<div className="text-lg font-bold text-[var(--text)]">{String(value)}</div>
								<div className="text-[10px] text-[var(--muted)] uppercase tracking-wide">{key}</div>
							</div>
						))}
					</div>
				</div>
			)}

			{/* STDOUT Tail - Syntax Highlighted */}
			{stdout_tail && (
				<div>
					<div className="text-[var(--text)] font-semibold mb-2 flex items-center gap-2">
						<span>📝</span> Output Log
						<span className="text-[10px] text-[var(--muted)] font-normal">(last 10 lines, 200 char limit)</span>
					</div>
					<div className="font-mono bg-black/50 p-3 rounded border border-[#1e293b] max-h-64 overflow-y-auto text-[11px] leading-relaxed">
						{formatLogTail(stdout_tail)}
					</div>
				</div>
			)}

			{/* STDERR Tail */}
			{stderr_tail && (
				<div>
					<div className="text-red-400 font-semibold mb-2 flex items-center gap-2">
						<span>⚠️</span> Error Log
						<span className="text-[10px] text-[var(--muted)] font-normal">(last 10 lines, 200 char limit)</span>
					</div>
					<div className="font-mono bg-red-900/20 border border-red-500/30 p-3 rounded max-h-64 overflow-y-auto text-[11px] leading-relaxed text-red-300">
						{formatLogTail(stderr_tail)}
					</div>
				</div>
			)}

			{/* Error Details (error_type, error_message, exception) */}
			{(error_type || error_message || exception) && (
				<div className="bg-red-900/10 border border-red-500/30 rounded p-3">
					<div className="text-red-400 font-semibold mb-2 flex items-center gap-2">
						<span>❌</span> Error Details
					</div>
					<div className="space-y-2 text-[11px]">
						{error_type && (
							<div>
								<span className="text-[var(--muted)]">Type: </span>
								<span className="text-red-400 font-semibold">{error_type}</span>
							</div>
						)}
						{error_message && (
							<div>
								<div className="text-[var(--muted)] mb-1">Message:</div>
								<div className="font-mono bg-black/30 p-2 rounded text-red-300 max-h-32 overflow-y-auto">
									{formatLogTail(error_message)}
								</div>
							</div>
						)}
						{exception && exception !== error_message && (
							<div>
								<div className="text-[var(--muted)] mb-1">Exception:</div>
								<div className="font-mono bg-black/30 p-2 rounded text-red-300 max-h-32 overflow-y-auto">
									{formatLogTail(exception)}
								</div>
							</div>
						)}
					</div>
				</div>
			)}

			{/* Other Fields */}
			{Object.keys(otherFields).length > 0 && (
				<details className="cursor-pointer group">
					<summary className="text-[var(--muted)] hover:text-[var(--text)] font-semibold list-none flex items-center gap-2">
						<span className="group-open:rotate-90 transition-transform">▶</span>
						Additional Fields ({Object.keys(otherFields).length})
					</summary>
					<pre className="mt-2 font-mono bg-black/50 p-3 rounded border border-[#1e293b] overflow-auto max-h-32 text-[11px]">
						{JSON.stringify(otherFields, null, 2)}
					</pre>
				</details>
			)}
		</div>
	);
}
