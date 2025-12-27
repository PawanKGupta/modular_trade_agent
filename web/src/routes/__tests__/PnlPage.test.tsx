import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { PnlPage } from '../dashboard/PnlPage';

// Mock the API
vi.mock('@/api/pnl', () => ({
	getPnlSummary: vi.fn(() =>
		Promise.resolve({
			totalPnl: 15000.50,
			daysGreen: 12,
			daysRed: 5,
			tradesGreen: 12,
			tradesRed: 5,
			totalRealizedPnl: 12000,
			totalUnrealizedPnl: 3000.50,
			avgTradePnl: 487.5,
			minTradePnl: -1200.50,
			maxTradePnl: 2500.75,
		})
	),
	getDailyPnl: vi.fn(() =>
		Promise.resolve([
			{ date: '2025-11-26', pnl: 2500.75 },
			{ date: '2025-11-25', pnl: -1200.50 },
			{ date: '2025-11-24', pnl: 3000.00 },
			{ date: '2025-11-23', pnl: -500.25 },
		])
	),
}));

describe('PnlPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
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
			expect(screen.getByText('Total P&L')).toBeInTheDocument();
			expect(screen.getByText('Profitable Trades')).toBeInTheDocument();
			expect(screen.getByText('Loss Trades')).toBeInTheDocument();
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

		await waitFor(() => {
			expect(screen.getByText('Daily P&L')).toBeInTheDocument();

			// Check dates are displayed
			expect(screen.getByText('2025-11-26')).toBeInTheDocument();
			expect(screen.getByText('2025-11-25')).toBeInTheDocument();

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
		vi.mocked(pnlApi.getDailyPnl).mockResolvedValueOnce([]);

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
			// Find all elements with negative P&L money value and get the one in the table
			const negativePnls = screen.getAllByText('Rs -1,200.50');
			expect(negativePnls.length).toBeGreaterThan(0);
			// The table cell should contain red color
			const tableCell = negativePnls.find((el) => el.className.includes('red'));
			expect(tableCell).toBeInTheDocument();
		});
	});
});
