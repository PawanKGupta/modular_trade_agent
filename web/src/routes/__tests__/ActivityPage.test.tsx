import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { ActivityPage } from '../dashboard/ActivityPage';

describe('ActivityPage', () => {
	it('filters by level and shows rows', async () => {
		render(withProviders(<ActivityPage />));
		await screen.findByText(/Recent Activity/i);
		// default includes all
		await screen.findByText(/User logged in/i);
		// filter to error
		fireEvent.change(screen.getByLabelText(/Level/i), { target: { value: 'error' } });
		await screen.findByText(/Broker connection failed/i);
	});
});
