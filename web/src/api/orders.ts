import { api } from './client';

export type OrderStatus = 'amo' | 'ongoing' | 'sell' | 'closed';

export interface Order {
	id: number;
	symbol: string;
	side: 'buy' | 'sell';
	qty: number;
	price: number;
	status: OrderStatus;
	created_at: string;
	updated_at: string;
}

export async function listOrders(status?: OrderStatus): Promise<Order[]> {
	const params = status ? { status } : undefined;
	const { data } = await api.get<Order[]>('/user/orders', { params });
	return data;
}
