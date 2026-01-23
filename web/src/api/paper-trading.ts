import { api } from './client';

export interface PaperTradingAccount {
	initial_capital: number;
	available_cash: number;
	total_pnl: number;
	realized_pnl: number;
	unrealized_pnl: number;
	portfolio_value: number;
	total_value: number;
	return_percentage: number;
}

export interface ReentryDetail {
	qty: number;
	price: number;
	time: string;
	level?: number;  // RSI level (30, 20, 10)
	cycle?: number;  // Re-entry cycle number
	rsi?: number;  // RSI value at re-entry
}

export interface PaperTradingHolding {
	symbol: string;
	quantity: number;
	average_price: number;
	current_price: number;
	cost_basis: number;
	market_value: number;
	pnl: number;
	pnl_percentage: number;
	target_price: number | null;  // Frozen EMA9 target
	distance_to_target: number | null;  // % to reach target
	reentry_count?: number;  // Number of re-entries
	reentries?: ReentryDetail[] | null;  // Re-entry details array
	entry_rsi?: number | null;  // RSI10 at initial entry
	initial_entry_price?: number | null;  // Initial entry price (before re-entries)
}

export interface PaperTradingOrder {
	order_id: string;
	symbol: string;
	transaction_type: string;
	quantity: number;
	order_type: string;
	status: string;
	execution_price: number | null;
	created_at: string;
	executed_at: string | null;
	metadata?: {
		entry_type?: string;
		rsi_level?: number;
		rsi_value?: number;
		original_ticker?: string;
		exit_reason?: string;
	};
}

export interface PaginatedPaperTradingOrders {
	items: PaperTradingOrder[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
}

export interface PaperTradingPortfolio {
	account: PaperTradingAccount;
	holdings: PaperTradingHolding[];
	recent_orders: PaginatedPaperTradingOrders;
	order_statistics: {
		total_orders: number;
		buy_orders: number;
		sell_orders: number;
		completed_orders: number;
		pending_orders: number;
		cancelled_orders: number;
		rejected_orders: number;
		success_rate: number;
		reentry_orders: number;
	};
}

export interface PaperTradingTransaction {
	order_id: string;
	symbol: string;
	transaction_type: string;
	quantity: number;
	price: number;
	order_value: number;
	charges: number;
	timestamp: string;
	// Optional fields for sell transactions
	entry_price?: number;
	exit_price?: number;
	realized_pnl?: number;
	pnl_percentage?: number;
	exit_reason?: string;
}

export interface ClosedPosition {
	symbol: string;
	entry_price: number;
	exit_price: number;
	quantity: number;
	buy_date: string;
	sell_date: string;
	holding_days: number;
	realized_pnl: number;
	pnl_percentage: number;
	charges: number;
}

export interface TradeHistoryStatistics {
	total_trades: number;
	profitable_trades: number;
	losing_trades: number;
	breakeven_trades: number;
	win_rate: number;
	total_profit: number;
	total_loss: number;
	net_pnl: number;
	avg_profit_per_trade: number;
	avg_loss_per_trade: number;
	total_transactions: number;
}

export interface PaginatedClosedPositions {
	items: ClosedPosition[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
}

export interface PaginatedTransactions {
	items: PaperTradingTransaction[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
}

export interface TradeHistory {
	transactions: PaginatedTransactions;
	closed_positions: PaginatedClosedPositions;
	statistics: TradeHistoryStatistics;
}

export interface GetPaperTradingPortfolioParams {
	page?: number;
	page_size?: number;
}

export interface GetPaperTradingHistoryParams {
	positions_page?: number;
	positions_page_size?: number;
	transactions_page?: number;
	transactions_page_size?: number;
}

export async function getPaperTradingPortfolio(
	params?: GetPaperTradingPortfolioParams
): Promise<PaperTradingPortfolio> {
	const res = await api.get('/user/paper-trading/portfolio', { params });
	return res.data;
}

export async function getPaperTradingHistory(
	params?: GetPaperTradingHistoryParams
): Promise<TradeHistory> {
	const res = await api.get('/user/paper-trading/history', { params });
	return res.data;
}
