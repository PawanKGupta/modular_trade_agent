import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { AdminUsersPage } from '../dashboard/AdminUsersPage';

describe('AdminUsersPage', () => {
	it('renders users and allows basic actions', async () => {
		// Minimal provider wrapper for this unit test
		render(withProviders(<AdminUsersPage />));

		await screen.findByText(/All users/i);
		// from MSW handlers
		await screen.findByText('admin@example.com');
		await screen.findByText('user@example.com');

		expect(screen.getByText(/Create user/i)).toBeInTheDocument();

		// role guard: page visible for admin (from MSW me handler setting admin role)
		expect(screen.queryByText(/You do not have permission/i)).toBeNull();
	});
});
