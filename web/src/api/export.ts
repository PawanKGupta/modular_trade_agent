import { api } from './client';

export interface ExportParams {
  startDate?: string; // YYYY-MM-DD format
  endDate?: string; // YYYY-MM-DD format
  tradeMode?: 'paper' | 'broker';
  status?: string;
  verdict?: string;
  includeUnrealized?: boolean;
}

/**
 * Download a file from a blob response
 */
function downloadFile(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/**
 * Generic export function using axios client
 */
async function exportCsv(endpoint: string, params: Record<string, string | number | boolean | undefined> = {}): Promise<void> {
  // Filter out undefined values
  const filteredParams = Object.entries(params)
    .filter(([_, value]) => value !== undefined)
    .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});

  const response = await api.get(`/user/export${endpoint}`, {
    params: filteredParams,
    responseType: 'blob',
  });

  // Extract filename from Content-Disposition header if available
  const contentDisposition = response.headers['content-disposition'];
  let filename = 'export.csv';
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^"]+)"?/);
    if (match) {
      filename = match[1];
    }
  }

  downloadFile(response.data, filename);
}

/**
 * Export P&L data as CSV
 */
export async function exportPnl(params: ExportParams = {}): Promise<void> {
  return exportCsv('/pnl/csv', {
    start_date: params.startDate,
    end_date: params.endDate,
    trade_mode: params.tradeMode ?? 'paper',
    include_unrealized: params.includeUnrealized ?? true,
  });
}

/**
 * Export trade history as CSV
 */
export async function exportTradeHistory(params: ExportParams = {}): Promise<void> {
  return exportCsv('/trades/csv', {
    start_date: params.startDate,
    end_date: params.endDate,
    trade_mode: params.tradeMode ?? 'paper',
  });
}

/**
 * Export signals/buying zone data as CSV
 */
export async function exportSignals(params: ExportParams = {}): Promise<void> {
  return exportCsv('/signals/csv', {
    start_date: params.startDate,
    end_date: params.endDate,
    verdict: params.verdict,
  });
}

/**
 * Export orders as CSV
 */
export async function exportOrders(params: ExportParams = {}): Promise<void> {
  return exportCsv('/orders/csv', {
    start_date: params.startDate,
    end_date: params.endDate,
    trade_mode: params.tradeMode ?? 'paper',
    status: params.status,
  });
}

/**
 * Export current portfolio holdings as CSV
 */
export async function exportPortfolio(params: ExportParams = {}): Promise<void> {
  return exportCsv('/portfolio/csv', {
    trade_mode: params.tradeMode ?? 'paper',
  });
}
