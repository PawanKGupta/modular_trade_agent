import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { OrdersPage } from '../dashboard/OrdersPage';

describe('OrdersPage', () => {
	it('switches tabs and displays orders for each status', async () => {
		render(withProviders(<OrdersPage />));

		// Default AMO
		await screen.findByText(/AMO Orders/i);
		await screen.findByText('INFY');
		await screen.findByText('1500.00');

		// Ongoing
		fireEvent.click(screen.getByRole('button', { name: 'Ongoing' }));
		await screen.findByText(/Ongoing Orders/i);
		await screen.findByText('RELIANCE');

		// Pending Execution
		fireEvent.click(screen.getByRole('button', { name: 'Pending Execution' }));
		await screen.findByText(/Pending Execution Orders/i);
		await screen.findByText('SUNPHARMA');

		// Sell
		fireEvent.click(screen.getByRole('button', { name: 'Sell' }));
		await screen.findByText(/Sell Orders/i);
		await screen.findByText('TCS');

		// Closed
		fireEvent.click(screen.getByRole('button', { name: 'Closed' }));
		await screen.findByText(/Closed Orders/i);
		await screen.findByText('HDFCBANK');
	});
});
