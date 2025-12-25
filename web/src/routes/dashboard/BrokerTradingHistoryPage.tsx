import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBrokerHistory } from '@/api/broker';
import type { BrokerHistory } from '@/api/broker';

function formatMoney(amount: number): string {
  return `Rs ${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  try {
    return new Date(dateStr).toLocaleString('en-IN');
  } catch {
    return dateStr;
  }
}

export function BrokerTradingHistoryPage() {
  const { data, isLoading, error, refetch, dataUpdatedAt } = useQuery<BrokerHistory>({
    queryKey: ['broker-history'],
    queryFn: () => getBrokerHistory(),
    refetchInterval: 30000,
  });

  useEffect(() => {
    document.title = 'Broker Trading History';
  }, []);

  const lastUpdate = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : 'Never';

  if (error) {
    return <div className="p-4 text-sm text-red-400">Failed to load broker history</div>;
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Broker Trading History</h1>
        <div className="flex items-center gap-3">
          <div className="text-xs text-[var(--muted)]">Last update: {lastUpdate}</div>
          <button onClick={() => refetch()} className="px-3 py-1 bg-[var(--accent)] rounded text-white">Refresh</button>
        </div>
      </div>

      {isLoading && <div className="text-sm text-[var(--muted)]">Loading...</div>}

      {data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-[var(--panel)] p-3 rounded border">Total Trades: {data.statistics.total_trades}</div>
            <div className="bg-[var(--panel)] p-3 rounded border">Closed Positions: {data.statistics.closed_positions}</div>
            <div className="bg-[var(--panel)] p-3 rounded border">Win Rate: {data.statistics.win_rate}%</div>
          </div>

          <div className="bg-[var(--panel)] rounded border p-2">
            <div className="font-medium p-2">Closed Positions ({data.closed_positions.length})</div>
            {data.closed_positions.length === 0 && <div className="p-2 text-[var(--muted)]">No closed positions</div>}
            {data.closed_positions.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#0f172a] text-[var(--muted)]">
                    <tr>
                      <th className="text-left p-2">Symbol</th>
                      <th className="text-right p-2">Qty</th>
                      <th className="text-right p-2">Entry</th>
                      <th className="text-right p-2">Exit</th>
                      <th className="text-right p-2">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.closed_positions.map((p) => (
                      <tr key={p.id} className="border-t border-[#1e293b]">
                        <td className="p-2 text-[var(--text)]">{p.symbol}</td>
                        <td className="p-2 text-right">{p.quantity}</td>
                        <td className="p-2 text-right">{formatMoney(p.avg_price)}</td>
                        <td className="p-2 text-right">{p.exit_price ? formatMoney(p.exit_price) : '-'}</td>
                        <td className={`p-2 text-right ${p.realized_pnl && p.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {p.realized_pnl ? formatMoney(p.realized_pnl) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="bg-[var(--panel)] rounded border p-2">
            <div className="font-medium p-2">Transactions ({data.transactions.length})</div>
            {data.transactions.length === 0 && <div className="p-2 text-[var(--muted)]">No transactions</div>}
            {data.transactions.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#0f172a] text-[var(--muted)]">
                    <tr>
                      <th className="text-left p-2">Time</th>
                      <th className="text-left p-2">Symbol</th>
                      <th className="text-left p-2">Side</th>
                      <th className="text-right p-2">Qty</th>
                      <th className="text-right p-2">Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.transactions.map((t) => (
                      <tr key={t.id} className="border-t border-[#1e293b]">
                        <td className="p-2 text-xs">{formatDate(t.placed_at)}</td>
                        <td className="p-2 font-medium">{t.symbol}</td>
                        <td className={`p-2 ${t.side === 'buy' ? 'text-green-400' : 'text-red-400'}`}>{t.side.toUpperCase()}</td>
                        <td className="p-2 text-right">{t.quantity ?? '-'}</td>
                        <td className="p-2 text-right">{t.execution_price ? formatMoney(t.execution_price) : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
