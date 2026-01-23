import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { TargetsPage } from '../dashboard/TargetsPage';

// Mock the API
vi.mock('@/api/targets', () => ({
	listTargets: vi.fn(() =>
		Promise.resolve([
			{
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
			},
			{
				id: 2,
				symbol: 'INFY',
				entry_price: 1600,
				current_price: 1620,
				target_price: 1700,
				quantity: 5,
				is_active: true,
				achieved_at: null,
				created_at: new Date().toISOString(),
				updated_at: new Date().toISOString(),
			},
		])
	),
}));

describe('TargetsPage', () => {
	it('renders target rows', async () => {
		render(withProviders(<TargetsPage />));
		await screen.findByText(/Price Targets/i);
		await screen.findByText('TCS');
		await screen.findByText('INFY');
	});
});
