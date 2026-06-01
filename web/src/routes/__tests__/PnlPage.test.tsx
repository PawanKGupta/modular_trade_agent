import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { PnlPage } from '../dashboard/PnlPage';

vi.mock('@/api/export', () => ({ exportPnl: vi.fn() }));
vi.mock('@/api/reports', () => ({ exportPnlPdf: vi.fn() }));
vi.mock('recharts', () => ({
	ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
	LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="pnl-trend">{children}</div>,
	Line: () => null,
	XAxis: () => null,
	YAxis: () => null,
	CartesianGrid: () => null,
	Tooltip: () => null,
	Legend: () => null,
	ReferenceLine: () => null,
}));

// Mock the API
vi.mock('@/api/pnl', () => ({
	getPnlSummary: vi.fn(),
	getDailyPnl: vi.fn(),
	getClosedPositions: vi.fn(),
}));

const closedPositionsMock = {
	items: [
		{
			id: 1,
			symbol: 'INFY',
			stock_name: 'Infosys',
			quantity: 10,
			avg_price: 1500,
			exit_price: 1550,
			opened_at: '2025-11-01T09:00:00',
			closed_at: '2025-11-10T15:00:00',
			realized_pnl: 500,
			realized_pnl_pct: 3.3,
			exit_reason: 'Target',
		},
	],
	total: 15,
	page: 1,
	page_size: 10,
	total_pages: 2,
};

describe('PnlPage', () => {
	beforeEach(async () => {
		vi.clearAllMocks();
		const pnlApi = await import('@/api/pnl');
		vi.mocked(pnlApi.getPnlSummary).mockResolvedValue({
			totalPnl: 15000.5,
			daysGreen: 12,
			daysRed: 5,
			tradesGreen: 12,
			tradesRed: 5,
			totalRealizedPnl: 12000,
			totalUnrealizedPnl: 3000.5,
			avgTradePnl: 487.5,
			minTradePnl: -1200.5,
			maxTradePnl: 2500.75,
		});
		vi.mocked(pnlApi.getDailyPnl).mockResolvedValue([
			{
				date: '2025-11-26',
				pnl: 2500.75,
				realized_pnl: 2000,
				unrealized_pnl: 500.75,
				fees: 20,
				trades_count: 2,
				symbols: ['INFY', 'TCS', 'HDFC', 'WIPRO'],
			},
			{ date: '2025-11-25', pnl: -1200.5, realized_pnl: -1200.5, unrealized_pnl: 0, fees: 5, trades_count: 1, symbols: [] },
			{ date: '2025-11-24', pnl: 3000.0, realized_pnl: 3000, unrealized_pnl: 0, fees: 8, trades_count: 3, symbols: ['RELIANCE'] },
			{ date: '2025-11-23', pnl: -500.25, realized_pnl: -500.25, unrealized_pnl: 0, fees: 4, trades_count: 1, symbols: [] },
		]);
		vi.mocked(pnlApi.getClosedPositions).mockResolvedValue(closedPositionsMock);
	});

	it('renders page title with live indicator', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			expect(screen.getByText('Profit & Loss')).toBeInTheDocument();
			expect(screen.getByText(/Live/i)).toBeInTheDocument();
			expect(screen.getByText(/Last update:/i)).toBeInTheDocument();
		});
	});

	it('displays summary section with formatted values', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			expect(screen.getByText('Summary')).toBeInTheDocument();

			const summaryHeader = screen.getByText('Summary');
			const summaryPanel = summaryHeader.closest('div')?.parentElement?.parentElement;
			expect(summaryPanel).toBeTruthy();

			const summary = summaryPanel as HTMLElement;
			expect(within(summary).getByText('Total P&L')).toBeInTheDocument();
			expect(within(summary).getByText('Profitable Trades')).toBeInTheDocument();
			expect(within(summary).getByText('Loss Trades')).toBeInTheDocument();
		});

		// Check formatted money value
		await waitFor(() => {
			expect(screen.getByText('Rs 15,000.50')).toBeInTheDocument();
			expect(screen.getByText('12')).toBeInTheDocument(); // Green trades
			expect(screen.getByText('5')).toBeInTheDocument(); // Red trades
		});
	});

	it('applies color coding to positive total P&L', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			const totalPnl = screen.getByText('Rs 15,000.50');
			expect(totalPnl.className).toContain('green'); // Positive P&L should be green
		});
	});

	it('displays daily P&L with formatted values and color coding', async () => {
		render(withProviders(<PnlPage />));

		const formatDate = (iso: string) =>
			new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

		await waitFor(() => {
			expect(screen.getByText('Daily P&L')).toBeInTheDocument();

			// Check dates are displayed
			expect(screen.getByText(formatDate('2025-11-26'))).toBeInTheDocument();
			expect(screen.getByText(formatDate('2025-11-25'))).toBeInTheDocument();

			// Check formatted money values using getAllByText for dates that appear in multiple places
			const allByText = screen.getAllByText('Rs 2,500.75');
			expect(allByText.length).toBeGreaterThan(0);
		});
	});

	it('displays status badges for profit and loss', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			const profitBadges = screen.getAllByText('Profit');
			expect(profitBadges.length).toBe(2); // 2 profitable days

			const lossBadges = screen.getAllByText('Loss');
			expect(lossBadges.length).toBe(2); // 2 loss days
		});
	});

	it('shows refresh button', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			const refreshButton = screen.getByRole('button', { name: /Refresh/i });
			expect(refreshButton).toBeInTheDocument();
		});
	});

	it('shows empty state when no daily P&L data', async () => {
		// Override mock for this test
		const pnlApi = await import('@/api/pnl');
		vi.mocked(pnlApi.getDailyPnl).mockResolvedValue([]);

		render(withProviders(<PnlPage />));

		await waitFor(() => {
			expect(screen.getByText(/No P&L data available/i)).toBeInTheDocument();
		});
	});

	it('applies correct color classes to positive P&L rows', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			// Find all elements with positive P&L money value and get the one in the table
			const positivePnls = screen.getAllByText('Rs 2,500.75');
			expect(positivePnls.length).toBeGreaterThan(0);
			// The table cell should contain green color
			const tableCell = positivePnls.find((el) => el.className.includes('green'));
			expect(tableCell).toBeInTheDocument();
		});
	});

	it('applies correct color classes to negative P&L rows', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			const negativePnls = screen.getAllByText('Rs -1,200.50');
			expect(negativePnls.length).toBeGreaterThan(0);
			const tableCell = negativePnls.find((el) => el.className.includes('red'));
			expect(tableCell).toBeInTheDocument();
		});
	});

	it('renders closed positions and export options', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			expect(screen.getByText('Closed Positions')).toBeInTheDocument();
			expect(screen.getAllByText('INFY').length).toBeGreaterThan(0);
		});

		fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'paper' } });
		fireEvent.click(screen.getByLabelText(/Include Unrealized/i));
		fireEvent.click(screen.getByRole('button', { name: /Export Options/i }));

		expect(screen.getByText('Export P&L Data')).toBeInTheDocument();
	});

	it('paginates closed positions and sorts columns', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			expect(screen.getByText(/Showing 1 to 10 of 15/i)).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await waitFor(async () => {
			const pnlApi = await import('@/api/pnl');
			expect(pnlApi.getClosedPositions).toHaveBeenCalledWith(2, 10, undefined, 'closed_at', 'desc');
		});

		const symbolHeaders = screen.getAllByRole('columnheader', { name: /Symbol/i });
		fireEvent.click(symbolHeaders[symbolHeaders.length - 1]);
		const pnlHeader = screen.getAllByRole('columnheader').find((el) => el.textContent?.trim() === 'P&L');
		expect(pnlHeader).toBeTruthy();
		fireEvent.click(pnlHeader!);
	});

	it('triggers CSV and PDF export', async () => {
		render(withProviders(<PnlPage />));
		await waitFor(() => expect(screen.getByText('Profit & Loss')).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: /Export Options/i }));
		const exportApi = await import('@/api/export');
		const reportsApi = await import('@/api/reports');
		vi.mocked(exportApi.exportPnl).mockResolvedValue(undefined);
		vi.mocked(reportsApi.exportPnlPdf).mockResolvedValue(undefined);

		fireEvent.click(screen.getByRole('button', { name: /Download CSV/i }));
		fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }));

		await waitFor(() => {
			expect(exportApi.exportPnl).toHaveBeenCalled();
			expect(reportsApi.exportPnlPdf).toHaveBeenCalled();
		});
	});

	it('shows empty closed positions message', async () => {
		const pnlApi = await import('@/api/pnl');
		vi.mocked(pnlApi.getClosedPositions).mockResolvedValue({
			items: [],
			total: 0,
			page: 1,
			page_size: 10,
			total_pages: 1,
		});

		render(withProviders(<PnlPage />));
		await waitFor(() => {
			expect(screen.getByText(/No closed positions available/i)).toBeInTheDocument();
		});
	});

	it('renders trend chart and supports daily sorting and broker mode', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			expect(screen.getByTestId('pnl-trend')).toBeInTheDocument();
		});

		fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'broker' } });
		fireEvent.click(screen.getByLabelText(/Include Unrealized/i));

		const totalPnlHeader = screen.getByRole('columnheader', { name: /Total P&L/i });
		fireEvent.click(totalPnlHeader);
		fireEvent.click(totalPnlHeader);

		await waitFor(async () => {
			const pnlApi = await import('@/api/pnl');
			expect(pnlApi.getPnlSummary).toHaveBeenCalledWith(undefined, undefined, 'broker', true);
		});
	});

	it('sorts daily table by date and changes closed positions page size', async () => {
		render(withProviders(<PnlPage />));
		await waitFor(() => expect(screen.getByText('Daily P&L')).toBeInTheDocument());

		const dailyPanel = screen.getByText('Daily P&L').closest('div.bg-\\[var\\(--panel\\)\\]') as HTMLElement;
		const dateHeader = within(dailyPanel).getAllByRole('columnheader').find((h) =>
			h.textContent?.trim().startsWith('Date')
		);
		expect(dateHeader).toBeTruthy();
		fireEvent.click(dateHeader!);
		fireEvent.click(dateHeader!);

		await waitFor(() => expect(screen.getByText(/Showing 1 to 10 of 15/i)).toBeInTheDocument());
		const pageSizeSelect = screen.getAllByRole('combobox')[1];
		fireEvent.change(pageSizeSelect, { target: { value: '25' } });

		await waitFor(async () => {
			const pnlApi = await import('@/api/pnl');
			expect(pnlApi.getClosedPositions).toHaveBeenCalledWith(1, 25, undefined, 'closed_at', 'desc');
		});
	});

	it('shows closed positions load error', async () => {
		const pnlApi = await import('@/api/pnl');
		vi.mocked(pnlApi.getClosedPositions).mockRejectedValue(new Error('load fail'));

		render(withProviders(<PnlPage />));
		await waitFor(() => expect(screen.getByText(/Failed to load/i)).toBeInTheDocument());
	});

	it('navigates closed positions pagination with previous button', async () => {
		render(withProviders(<PnlPage />));
		await waitFor(() => expect(screen.getByText(/Showing 1 to 10 of 15/i)).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await waitFor(async () => {
			const pnlApi = await import('@/api/pnl');
			expect(pnlApi.getClosedPositions).toHaveBeenCalledWith(2, 10, undefined, 'closed_at', 'desc');
		});

		fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
		await waitFor(async () => {
			const pnlApi = await import('@/api/pnl');
			expect(pnlApi.getClosedPositions).toHaveBeenCalledWith(1, 10, undefined, 'closed_at', 'desc');
		});

		const closedDateHeader = screen.getAllByRole('columnheader').find((el) =>
			el.textContent?.includes('Closed Date')
		);
		expect(closedDateHeader).toBeTruthy();
		fireEvent.click(closedDateHeader!);
		fireEvent.click(closedDateHeader!);
	});

	it('navigates multi-page closed positions via page number buttons', async () => {
		const pnlApi = await import('@/api/pnl');
		vi.mocked(pnlApi.getClosedPositions).mockResolvedValue({
			...closedPositionsMock,
			total: 60,
			total_pages: 6,
		});

		render(withProviders(<PnlPage />));
		await waitFor(() => expect(screen.getByText(/Showing 1 to 10 of 60/i)).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await waitFor(() => expect(screen.getByText(/Showing 11 to 20 of 60/i)).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await waitFor(() => {
			expect(pnlApi.getClosedPositions).toHaveBeenCalledWith(3, 10, undefined, 'closed_at', 'desc');
			expect(screen.getByText(/Showing 21 to 30 of 60/i)).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: '4' }));
		await waitFor(() => {
			expect(pnlApi.getClosedPositions).toHaveBeenCalledWith(4, 10, undefined, 'closed_at', 'desc');
		});
	});
});
