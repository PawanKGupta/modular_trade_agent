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
			expect(screen.getByText('Profitable Days')).toBeInTheDocument();
			expect(screen.getByText('Loss Days')).toBeInTheDocument();
		});

		// Check formatted money value
		await waitFor(() => {
			expect(screen.getByText('Rs 15,000.50')).toBeInTheDocument();
			expect(screen.getByText('12')).toBeInTheDocument(); // Green days
			expect(screen.getByText('5')).toBeInTheDocument(); // Red days
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

			// Check formatted money values
			expect(screen.getByText('Rs 2,500.75')).toBeInTheDocument();
			expect(screen.getByText('Rs -1,200.50')).toBeInTheDocument();
			expect(screen.getByText('Rs 3,000.00')).toBeInTheDocument();
			expect(screen.getByText('Rs -500.25')).toBeInTheDocument();
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
		vi.mocked(await import('@/api/pnl')).getDailyPnl.mockResolvedValueOnce([]);

		render(withProviders(<PnlPage />));

		await waitFor(() => {
			expect(screen.getByText('No P&L data available')).toBeInTheDocument();
		});
	});

	it('applies correct color classes to positive P&L rows', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			const positivePnl = screen.getByText('Rs 2,500.75');
			expect(positivePnl.className).toContain('green');
		});
	});

	it('applies correct color classes to negative P&L rows', async () => {
		render(withProviders(<PnlPage />));

		await waitFor(() => {
			const negativePnl = screen.getByText('Rs -1,200.50');
			expect(negativePnl.className).toContain('red');
		});
	});
});
