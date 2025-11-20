import { Fragment, useState } from 'react';
import type { ErrorLogEntry } from '@/api/logs';

type Props = {
	errors: ErrorLogEntry[];
	isLoading?: boolean;
	isAdmin?: boolean;
	onResolve?: (error: ErrorLogEntry) => void;
};

export function ErrorLogTable({ errors, isLoading, isAdmin, onResolve }: Props) {
	const [expandedId, setExpandedId] = useState<number | null>(null);

	if (isLoading) {
		return <div className="text-sm text-[var(--muted)]">Loading error logs...</div>;
	}

	if (!errors.length) {
		return <div className="text-sm text-[var(--muted)]">No error logs found for the selected filters.</div>;
	}

	return (
		<div className="overflow-auto rounded border border-[#1f2937]">
			<table className="w-full text-sm text-left">
				<thead className="bg-[#0f172a] text-[var(--muted)]">
					<tr>
						<th className="px-3 py-2">Time</th>
						<th className="px-3 py-2">Type</th>
						<th className="px-3 py-2">Message</th>
						<th className="px-3 py-2">Status</th>
						{isAdmin && <th className="px-3 py-2">Actions</th>}
					</tr>
				</thead>
				<tbody>
					{errors.map((error) => {
						const isExpanded = expandedId === error.id;
						return (
							<Fragment key={error.id}>
								<tr key={error.id} className="border-t border-[#1f2937]">
									<td className="px-3 py-2 whitespace-nowrap">
										{new Date(error.occurred_at).toLocaleString()}
									</td>
									<td className="px-3 py-2 font-mono">{error.error_type}</td>
									<td className="px-3 py-2">
										<div>{error.error_message}</div>
										<button
											type="button"
											className="text-xs text-[var(--accent)] mt-1"
											onClick={() => setExpandedId(isExpanded ? null : error.id)}
										>
											{isExpanded ? 'Hide Details' : 'Show Details'}
										</button>
									</td>
									<td className="px-3 py-2">
										{error.resolved ? (
											<span className="text-green-400">Resolved</span>
										) : (
											<span className="text-red-400">Unresolved</span>
										)}
									</td>
									{isAdmin && (
										<td className="px-3 py-2">
											{!error.resolved && onResolve ? (
												<button
													type="button"
													className="text-xs px-2 py-1 rounded bg-[var(--accent)] text-black"
													onClick={() => onResolve(error)}
												>
													Resolve
												</button>
											) : (
												<span className="text-xs text-[var(--muted)]">-</span>
											)}
										</td>
									)}
								</tr>
								{isExpanded && (
									<tr className="border-t border-[#1f2937] bg-[#0f172a]/40">
										<td className="px-3 py-3 text-xs text-[var(--muted)]" colSpan={isAdmin ? 5 : 4}>
											<div className="mb-2">
												<strong>Traceback:</strong>
												<pre className="mt-1 whitespace-pre-wrap bg-black/30 p-2 rounded border border-black/50">
													{error.traceback ?? 'N/A'}
												</pre>
											</div>
											{error.context && (
												<div className="mb-2">
													<strong>Context:</strong>
													<pre className="mt-1">{JSON.stringify(error.context, null, 2)}</pre>
												</div>
											)}
											{error.resolution_notes && (
												<div>
													<strong>Resolution Notes:</strong>
													<p className="mt-1">{error.resolution_notes}</p>
												</div>
											)}
										</td>
									</tr>
								)}
							</Fragment>
						);
					})}
				</tbody>
			</table>
		</div>
	);
}
