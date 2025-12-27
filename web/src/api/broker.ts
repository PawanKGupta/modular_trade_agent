import { api } from './client';

export interface BrokerTransaction {
  id: number;
  symbol: string;
  side: string;
  quantity: number | null;
  avg_price: number | null;
  execution_price: number | null;
  status: string;
  placed_at: string | null;
  filled_at: string | null;
  closed_at: string | null;
  order_metadata?: Record<string, unknown>;
}

export interface BrokerClosedPosition {
  id: number;
  symbol: string;
  quantity: number;
  avg_price: number;
  opened_at: string | null;
  closed_at: string | null;
  exit_price: number | null;
  realized_pnl: number | null;
  realized_pnl_pct: number | null;
}

export interface BrokerHistoryStatistics {
  total_trades: number;
  closed_positions: number;
  win_rate: number;
  realized_pnl: number;
}

export interface BrokerHistory {
  transactions: BrokerTransaction[];
  closed_positions: BrokerClosedPosition[];
  statistics: BrokerHistoryStatistics;
}

export async function getBrokerHistory(params?: { from?: string; to?: string; limit?: number }): Promise<BrokerHistory> {
  const res = await api.get('/user/broker/history', { params });
  return res.data as BrokerHistory;
}
