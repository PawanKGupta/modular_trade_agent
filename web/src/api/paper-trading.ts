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
}

export interface PaperTradingPortfolio {
	account: PaperTradingAccount;
	holdings: PaperTradingHolding[];
	recent_orders: PaperTradingOrder[];
	order_statistics: {
		total_orders: number;
		buy_orders: number;
		sell_orders: number;
		completed_orders: number;
		pending_orders: number;
		cancelled_orders: number;
		rejected_orders: number;
		success_rate: number;
	};
}

export async function getPaperTradingPortfolio(): Promise<PaperTradingPortfolio> {
	const res = await api.get('/user/paper-trading/portfolio');
	return res.data;
}

