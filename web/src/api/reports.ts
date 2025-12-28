import { api } from './client';

export interface ReportParams {
  period?: 'daily' | 'weekly' | 'monthly' | 'custom';
  startDate?: string; // YYYY-MM-DD
  endDate?: string;   // YYYY-MM-DD
  tradeMode?: 'paper' | 'broker';
  includeUnrealized?: boolean;
}

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

export async function exportPnlPdf(params: ReportParams = {}): Promise<void> {
  const response = await api.get('/user/reports/pnl/pdf', {
    params: {
      period: params.period ?? 'custom',
      start_date: params.startDate,
      end_date: params.endDate,
      trade_mode: params.tradeMode ?? 'paper',
      include_unrealized: params.includeUnrealized ?? true,
    },
    responseType: 'blob',
  });

  const contentDisposition = response.headers['content-disposition'];
  let filename = 'pnl_report.pdf';
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^";]+)"?/);
    if (match) filename = match[1];
  }

  downloadFile(response.data, filename);
}
