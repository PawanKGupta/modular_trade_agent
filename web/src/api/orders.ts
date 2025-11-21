import { api } from './client';

export type OrderStatus =
	| 'amo'
	| 'ongoing'
	| 'sell'
	| 'closed'
	| 'failed'
	| 'retry_pending'
	| 'rejected'
	| 'pending_execution';

export interface Order {
	id: number;
	symbol: string;
	side: 'buy' | 'sell';
	quantity: number;
	price: number | null;
	status: OrderStatus;
	created_at: string | null;
	updated_at: string | null;
	// Order monitoring fields
	failure_reason?: string | null;
	first_failed_at?: string | null;
	last_retry_attempt?: string | null;
	retry_count?: number;
	rejection_reason?: string | null;
	cancelled_reason?: string | null;
	last_status_check?: string | null;
	execution_price?: number | null;
	execution_qty?: number | null;
	execution_time?: string | null;
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
