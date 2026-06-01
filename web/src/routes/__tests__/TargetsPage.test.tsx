import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { TargetsPage } from '../dashboard/TargetsPage';
import * as targetsApi from '@/api/targets';

vi.mock('@/api/targets', () => ({
	listTargets: vi.fn(),
}));

const activeTarget = {
	id: 1,
	symbol: 'TCS',
	entry_price: 3800,
	current_price: 3850,
	target_price: 3900,
	quantity: 10,
	is_active: true,
	achieved_at: null,
	created_at: new Date().toISOString(),
	updated_at: new Date().toISOString(),
};

const achievedTarget = {
	id: 2,
	symbol: 'INFY',
	entry_price: 1600,
	current_price: 1700,
	target_price: 1700,
	quantity: 5,
	is_active: false,
	achieved_at: '2025-01-15T10:00:00',
	created_at: new Date().toISOString(),
	updated_at: new Date().toISOString(),
};

describe('TargetsPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(targetsApi.listTargets).mockResolvedValue([activeTarget, achievedTarget]);
	});

	it('renders target rows with stats and achieved section', async () => {
		render(withProviders(<TargetsPage />));
		await waitFor(() => {
			expect(screen.getByText(/Price Targets/i)).toBeInTheDocument();
			expect(screen.getByText('TCS')).toBeInTheDocument();
			expect(screen.getByText('INFY')).toBeInTheDocument();
			expect(screen.getByText(/Active Targets \(1\)/i)).toBeInTheDocument();
			expect(screen.getByText(/Achieved Targets \(1\)/i)).toBeInTheDocument();
			expect(screen.getByText(/Success Rate/i)).toBeInTheDocument();
		});
	});

	it('shows loading state', async () => {
		vi.mocked(targetsApi.listTargets).mockImplementation(() => new Promise(() => {}));
		render(withProviders(<TargetsPage />));
		expect(screen.getByText(/Loading targets/i)).toBeInTheDocument();
	});

	it('shows empty state when no targets exist', async () => {
		vi.mocked(targetsApi.listTargets).mockResolvedValue([]);
		render(withProviders(<TargetsPage />));
		await waitFor(() => {
			expect(screen.getByText(/No price targets set yet/i)).toBeInTheDocument();
		});
	});

	it('shows error state and retries', async () => {
		vi.mocked(targetsApi.listTargets).mockRejectedValueOnce(new Error('fail'));
		render(withProviders(<TargetsPage />));
		await waitFor(() => expect(screen.getByText(/Failed to load targets/i)).toBeInTheDocument());

		vi.mocked(targetsApi.listTargets).mockResolvedValue([activeTarget]);
		fireEvent.click(screen.getByRole('button', { name: /Retry/i }));
		await waitFor(() => expect(screen.getByText('TCS')).toBeInTheDocument());
	});

	it('refreshes targets from header button', async () => {
		render(withProviders(<TargetsPage />));
		await waitFor(() => expect(screen.getByText('TCS')).toBeInTheDocument());

		const initialCalls = vi.mocked(targetsApi.listTargets).mock.calls.length;
		fireEvent.click(screen.getByRole('button', { name: /Refresh/i }));
		await waitFor(() => {
			expect(targetsApi.listTargets.mock.calls.length).toBeGreaterThan(initialCalls);
		});
	});
});
