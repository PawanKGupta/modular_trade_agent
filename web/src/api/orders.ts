import { api } from './client';

export type OrderStatus =
	| 'pending' // Merged: AMO + PENDING_EXECUTION
	| 'ongoing'
	| 'closed'
	| 'failed' // Merged: FAILED + RETRY_PENDING + REJECTED
	| 'cancelled';
	// Note: SELL status removed - use side='sell' to identify sell orders

export interface Order {
	id: number;
	symbol: string;
	side: 'buy' | 'sell';
	quantity: number;
	price: number | null;
	status: OrderStatus;
	created_at: string | null;
	updated_at: string | null;
	// Unified reason field (replaces failure_reason, rejection_reason, cancelled_reason)
	reason?: string | null;
	// Order monitoring fields
	first_failed_at?: string | null;
	last_retry_attempt?: string | null;
	retry_count?: number;
	last_status_check?: string | null;
	execution_price?: number | null;
	execution_qty?: number | null;
	execution_time?: string | null;
	// Legacy fields (deprecated, kept for backward compatibility)
	failure_reason?: string | null; // Deprecated: use reason
	rejection_reason?: string | null; // Deprecated: use reason
	cancelled_reason?: string | null; // Deprecated: use reason
}

export interface ListOrdersParams {
	status?: OrderStatus;
	failure_reason?: string;
	from_date?: string;
	to_date?: string;
}

export async function listOrders(params?: ListOrdersParams): Promise<Order[]> {
	const { data } = await api.get<Order[]>('/user/orders/', { params });
	return data;
}

export async function retryOrder(orderId: number): Promise<Order> {
	const { data } = await api.post<Order>(`/user/orders/${orderId}/retry`);
	return data;
}

export async function dropOrder(orderId: number): Promise<{ message: string }> {
	const { data } = await api.delete<{ message: string }>(`/user/orders/${orderId}`);
	return data;
}
