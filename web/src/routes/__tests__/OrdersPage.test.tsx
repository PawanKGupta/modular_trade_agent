import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { OrdersPage } from '../dashboard/OrdersPage';

describe('OrdersPage', () => {
	it('switches tabs and displays orders for each status', async () => {
		render(withProviders(<OrdersPage />));

		// Default Pending (merged: AMO + PENDING_EXECUTION)
		await screen.findByText(/Pending Orders/i);
		await screen.findByText('INFY');
		await screen.findByText('1500.00');

		// Ongoing
		fireEvent.click(screen.getByRole('button', { name: 'Ongoing' }));
		await screen.findByText(/Ongoing Orders/i);
		await screen.findByText('RELIANCE');

		// Failed (merged: FAILED + RETRY_PENDING + REJECTED)
		fireEvent.click(screen.getByRole('button', { name: 'Failed' }));
		await screen.findByText(/Failed Orders/i);
		await screen.findByText('TCS');

		// Closed
		fireEvent.click(screen.getByRole('button', { name: 'Closed' }));
		await screen.findByText(/Closed Orders/i);
		await screen.findByText('HDFCBANK');

		// Cancelled
		fireEvent.click(screen.getByRole('button', { name: 'Cancelled' }));
		await screen.findByText(/Cancelled Orders/i);
		await screen.findByText('WIPRO');
	});
});
