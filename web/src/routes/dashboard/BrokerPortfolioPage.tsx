import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPortfolio, type PaperTradingPortfolio } from '@/api/user';
import { useSettings } from '@/hooks/useSettings';
import { formatBrokerError, calculateRetryDelay } from '@/utils/brokerApi';
import { exportPortfolio } from '@/api/export';
import { ExportButton } from '@/components/ExportButton';

function formatMoney(amount: number): string {
	return `Rs ${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(value: number): string {
	return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

// Removed unused DateRangePicker and related state

export function BrokerPortfolioPage() {
	const { isBrokerMode, isBrokerConnected, broker } = useSettings();
	const [showExportOptions, setShowExportOptions] = useState(false);

	const { data, isLoading, error, refetch, dataUpdatedAt, failureCount } = useQuery<PaperTradingPortfolio>({
		queryKey: ['portfolio', 'broker'],
		queryFn: getPortfolio,
		refetchInterval: 30000, // Refresh every 30 seconds (reduced from 5s to avoid frequent auth/OTP)
		enabled: isBrokerMode && isBrokerConnected, // Only fetch if in broker mode and connected
		retry: (failureCount, error) => {
			// Retry up to 3 times for retryable errors
			if (failureCount >= 3) return false;
			const brokerError = formatBrokerError(error);
			return brokerError.retryable;
		},
		retryDelay: (attemptIndex) => calculateRetryDelay(attemptIndex),
	});

	useEffect(() => {
		document.title = 'Broker Portfolio';
	}, []);

	const handleExport = async () => {
		await exportPortfolio({
			tradeMode: 'broker',
		});
	};

	// Format last update time
	const lastUpdate = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : 'Never';

	if (!isBrokerMode) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-yellow-400">
					Broker portfolio is only available in broker mode. Please switch to broker mode in settings.
				</div>
			</div>
		);
	}

	if (!isBrokerConnected) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-yellow-400">
					Broker is not connected. Please configure and connect your broker in settings.
				</div>
			</div>
		);
	}

	if (isLoading) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-[var(--text)]">Loading portfolio...</div>
			</div>
		);
	}

	if (error) {
		const brokerError = formatBrokerError(error);
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-red-400">
					Error loading portfolio: {brokerError.message}
					{brokerError.statusCode && ` (Status: ${brokerError.statusCode})`}
					{failureCount && failureCount > 0 && ` (Retry attempt: ${failureCount})`}
				</div>
				{brokerError.retryable && (
					<div className="mt-2 text-xs text-yellow-400">
						This error is retryable. The system will automatically retry.
					</div>
				)}
				<button
					onClick={() => refetch()}
					className="mt-2 px-4 py-3 sm:py-2 bg-[var(--accent)] text-white rounded hover:opacity-90 text-sm sm:text-base min-h-[44px] sm:min-h-0"
				>
					Retry Now
				</button>
			</div>
		);
	}

	if (!data) {
		return (
			<div className="p-2 sm:p-4">
				<div className="text-xs sm:text-sm text-[var(--muted)]">No portfolio data available</div>
			</div>
		);
	}

	const { account, holdings } = data;

	return (
		<div className="p-2 sm:p-4 space-y-3 sm:space-y-4">
			<div className="flex flex-col gap-3">
				<div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
					<div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-3">
						<h1 className="text-lg sm:text-xl font-semibold text-[var(--text)]">
							Broker Portfolio {broker ? `(${broker.toUpperCase()})` : ''}
						</h1>
						<div className="flex items-center gap-2">
							<div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
							<span className="text-xs text-[var(--muted)]">
								Live • Last update: {lastUpdate}
							</span>
						</div>
					</div>
					<div className="flex items-center gap-2">
						<button
							onClick={() => setShowExportOptions(!showExportOptions)}
							className="px-3 py-2 sm:py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 min-h-[44px] sm:min-h-0"
						>
							Export {showExportOptions ? '▲' : '▼'}
						</button>
						<button
							onClick={() => refetch()}
							className="px-3 py-2 sm:py-1 text-sm bg-[var(--accent)] text-white rounded hover:opacity-90 min-h-[44px] sm:min-h-0 w-full sm:w-auto"
						>
							Refresh
						</button>
					</div>
				</div>

				{showExportOptions && (
					<div className="bg-[var(--panel)] border border-[#1e293b] rounded p-4">
						<h3 className="text-sm font-medium text-[var(--text)] mb-3">Export Portfolio</h3>
						<div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
							<ExportButton onExport={handleExport} label="Download CSV" />
						</div>
						<p className="text-xs text-[var(--muted)] mt-2">
							Export current broker portfolio holdings with P&L, quantities, and prices.
						</p>
					</div>
				)}
			</div>

			{/* Account Summary */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-sm sm:text-base text-[var(--text)]">Account Summary</div>
				</div>
				<div className="p-3 sm:p-4 grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Available Cash</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.available_cash)}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Portfolio Value</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.portfolio_value)}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Total Value</div>
						<div className="text-base sm:text-lg font-semibold text-[var(--text)]">
							{formatMoney(account.total_value)}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Total P&L</div>
						<div
							className={`text-base sm:text-lg font-semibold ${
								account.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatMoney(account.total_pnl)} ({formatPercent(account.return_percentage)})
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Realized P&L</div>
						<div
							className={`text-base sm:text-lg font-semibold ${
								account.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatMoney(account.realized_pnl)}
						</div>
					</div>
					<div>
						<div className="text-xs sm:text-sm text-[var(--muted)]">Unrealized P&L</div>
						<div
							className={`text-base sm:text-lg font-semibold ${
								account.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatMoney(account.unrealized_pnl)}
						</div>
					</div>
					<div>
						<div className="text-sm text-[var(--muted)]">Return</div>
						<div
							className={`text-lg font-semibold ${
								account.return_percentage >= 0 ? 'text-green-400' : 'text-red-400'
							}`}
						>
							{formatPercent(account.return_percentage)}
						</div>
					</div>
				</div>
			</div>

			{/* Holdings */}
			<div className="bg-[var(--panel)] border border-[#1e293b] rounded">
				<div className="px-3 py-2 border-b border-[#1e293b]">
					<div className="font-medium text-sm sm:text-base text-[var(--text)]">
						Holdings ({holdings.length})
					</div>
				</div>
				{holdings.length === 0 ? (
					<div className="p-3 sm:p-4 text-xs sm:text-sm text-[var(--muted)]">No holdings</div>
				) : (
					<div className="overflow-x-auto -mx-2 sm:mx-0">
						<table className="w-full text-xs sm:text-sm">
							<thead className="bg-[#0f172a] text-[var(--muted)]">
								<tr>
									<th className="text-left p-2 whitespace-nowrap">Symbol</th>
									<th className="text-right p-2 whitespace-nowrap">Qty</th>
									<th className="text-right p-2 whitespace-nowrap hidden sm:table-cell">Avg Price</th>
									<th className="text-right p-2 whitespace-nowrap">Current</th>
									<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Market Value</th>
									<th className="text-right p-2 whitespace-nowrap">P&L</th>
									<th className="text-right p-2 whitespace-nowrap">P&L %</th>
									<th className="text-right p-2 whitespace-nowrap hidden md:table-cell">Re-entries</th>
								</tr>
							</thead>
							<tbody>
								{holdings.map((h) => (
									<tr key={h.symbol} className="border-t border-[#1e293b]">
										<td className="p-2 text-[var(--text)] font-medium">{h.symbol}</td>
										<td className="p-2 text-right text-[var(--text)]">{h.quantity}</td>
										<td className="p-2 text-right text-[var(--text)]">
											<span className="font-mono">
												{h.average_price.toLocaleString('en-IN', {
													minimumFractionDigits: 2,
													maximumFractionDigits: 2,
												})}
											</span>
										</td>
										<td className="p-2 text-right text-[var(--text)]">
											<span className="font-mono">
												{h.current_price.toLocaleString('en-IN', {
													minimumFractionDigits: 2,
													maximumFractionDigits: 2,
												})}
											</span>
										</td>
										<td className="p-2 text-right text-[var(--text)]">
											<span className="font-mono">
												{h.market_value.toLocaleString('en-IN', {
													minimumFractionDigits: 2,
													maximumFractionDigits: 2,
												})}
											</span>
										</td>
										<td
											className={`p-2 text-right font-medium ${
												h.pnl >= 0 ? 'text-green-400' : 'text-red-400'
											}`}
										>
											<span className="font-mono">
												{h.pnl.toLocaleString('en-IN', {
													minimumFractionDigits: 2,
													maximumFractionDigits: 2,
												})}
											</span>
										</td>
										<td
											className={`p-2 text-right font-medium ${
												h.pnl_percentage >= 0 ? 'text-green-400' : 'text-red-400'
											}`}
										>
											{formatPercent(h.pnl_percentage)}
										</td>
										<td className="p-2 text-right text-[var(--text)] hidden md:table-cell">
											{(h.reentry_count && h.reentry_count > 0) || (h.reentries && h.reentries.length > 0) ? (
												<div className="flex flex-col items-end gap-1">
													{h.reentry_count && h.reentry_count > 0 && (
														<span className="text-xs font-medium text-yellow-400">
															{h.reentry_count} re-entry{h.reentry_count !== 1 ? 's' : ''}
														</span>
													)}
													{h.entry_rsi !== null && h.entry_rsi !== undefined && (
														<span className="text-xs text-[var(--muted)]">
															Entry RSI: {h.entry_rsi.toFixed(1)}
														</span>
													)}
													{h.reentries && h.reentries.length > 0 && (
														<details className="text-xs">
															<summary className="cursor-pointer text-yellow-400 hover:text-yellow-300">
																View details
															</summary>
															<div className="mt-1 space-y-1 text-left max-w-xs">
																{h.reentries.map((re, idx) => (
																	<div key={idx} className="text-[var(--muted)] border-b border-[#1e293b]/50 pb-1 mb-1 last:border-0 last:mb-0">
																		<div className="font-medium">
																			Re-entry {idx + 1}: {re.qty} @ Rs {typeof re.price === 'number' ? re.price.toFixed(2) : re.price}
																		</div>
																		{re.level && (
																			<div className="text-xs">
																				Level: {re.level} {re.rsi && `(RSI: ${typeof re.rsi === 'number' ? re.rsi.toFixed(1) : re.rsi})`}
																			</div>
																		)}
																		{re.time && (
																			<div className="text-xs">
																				{new Date(re.time).toLocaleDateString()}
																			</div>
																		)}
																	</div>
																))}
															</div>
														</details>
													)}
												</div>
											) : (
												<span className="text-[var(--muted)]">-</span>
											)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</div>
		</div>
	);
}
