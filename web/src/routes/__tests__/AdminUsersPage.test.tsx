import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { withProviders } from '@/test/utils';
import { AdminUsersPage } from '../dashboard/AdminUsersPage';
import * as adminApi from '@/api/admin';
import { useSessionStore } from '@/state/sessionStore';

vi.mock('@/api/admin', () => ({
	listUsers: vi.fn(),
	createUser: vi.fn(),
	updateUser: vi.fn(),
	deleteUser: vi.fn(),
}));

const sampleUsers = [
	{ id: 1, email: 'admin@example.com', name: 'Admin', role: 'admin' as const, is_active: true, mobile_number: null, created_at: '', updated_at: '' },
	{ id: 2, email: 'user@example.com', name: 'User', role: 'user' as const, is_active: true, mobile_number: '9876543210', created_at: '', updated_at: '' },
];

function getCreatePasswordInput() {
	return document.getElementById('admin-create-password') as HTMLInputElement;
}

describe('AdminUsersPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		useSessionStore.setState({
			isAdmin: true,
			user: { id: 1, email: 'admin@example.com', roles: ['admin'] } as never,
			isAuthenticated: true,
			hasHydrated: true,
			refresh: vi.fn().mockResolvedValue(undefined),
		});
		vi.mocked(adminApi.listUsers).mockResolvedValue(sampleUsers);
		vi.mocked(adminApi.createUser).mockResolvedValue(sampleUsers[1]);
		vi.mocked(adminApi.updateUser).mockResolvedValue(sampleUsers[1]);
		vi.mocked(adminApi.deleteUser).mockResolvedValue(undefined);
	});

	it('renders users list for admin', async () => {
		render(withProviders(<AdminUsersPage />));

		await waitFor(() => {
			expect(screen.getByText('admin@example.com')).toBeInTheDocument();
			expect(screen.getByText('user@example.com')).toBeInTheDocument();
			expect(screen.getByText('9876543210')).toBeInTheDocument();
		});
	});

	it('creates a new user', async () => {
		render(withProviders(<AdminUsersPage />));
		await waitFor(() => expect(screen.getByText('Create user')).toBeInTheDocument());

		await userEvent.type(screen.getByLabelText(/^Email/i), 'new@example.com');
		await userEvent.type(screen.getByLabelText(/^Name/i), 'New User');
		await userEvent.type(getCreatePasswordInput(), 'Secret123!');
		fireEvent.click(screen.getByRole('button', { name: 'Create' }));

		await waitFor(() => {
			expect(adminApi.createUser.mock.calls[0][0]).toEqual(
				expect.objectContaining({ email: 'new@example.com', password: 'Secret123!', name: 'New User' })
			);
		});
	});

	it('blocks create when name is missing', async () => {
		render(withProviders(<AdminUsersPage />));
		await waitFor(() => expect(screen.getByText('Create user')).toBeInTheDocument());

		await userEvent.type(screen.getByLabelText(/^Email/i), 'new@example.com');
		await userEvent.type(getCreatePasswordInput(), 'Secret123!');
		fireEvent.click(screen.getByRole('button', { name: 'Create' }));

		await waitFor(() => {
			expect(screen.getByText('Name is required')).toBeInTheDocument();
		});
		expect(adminApi.createUser).not.toHaveBeenCalled();
	});

	it('updates user role and active status', async () => {
		render(withProviders(<AdminUsersPage />));
		await waitFor(() => expect(screen.getByText('user@example.com')).toBeInTheDocument());

		const roleSelects = screen.getAllByRole('combobox');
		await userEvent.selectOptions(roleSelects[2], 'admin');

		await waitFor(() => {
			expect(adminApi.updateUser).toHaveBeenCalledWith(2, { role: 'admin' });
		});

		const checkboxes = screen.getAllByRole('checkbox');
		fireEvent.click(checkboxes[0]);

		await waitFor(() => {
			expect(adminApi.updateUser).toHaveBeenCalledWith(1, { is_active: false });
		});
	});

	it('deletes a user', async () => {
		render(withProviders(<AdminUsersPage />));
		await waitFor(() => expect(screen.getByText('user@example.com')).toBeInTheDocument());

		const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
		fireEvent.click(deleteButtons[1]);

		await waitFor(() => {
			expect(adminApi.deleteUser).toHaveBeenCalledWith(2);
		});
	});

	it('shows permission denied for non-admin', async () => {
		useSessionStore.setState({ isAdmin: false, user: null, isAuthenticated: false, hasHydrated: true });
		render(withProviders(<AdminUsersPage />));

		expect(screen.getByText(/You do not have permission/i)).toBeInTheDocument();
	});

	it('shows empty state when no users', async () => {
		vi.mocked(adminApi.listUsers).mockResolvedValue([]);
		render(withProviders(<AdminUsersPage />));

		await waitFor(() => {
			expect(screen.getByText('No users found')).toBeInTheDocument();
		});
	});

	it('shows create error state', async () => {
		vi.mocked(adminApi.createUser).mockRejectedValue(new Error('fail'));
		render(withProviders(<AdminUsersPage />));
		await waitFor(() => expect(screen.getByLabelText(/^Email/i)).toBeInTheDocument());

		await userEvent.type(screen.getByLabelText(/^Email/i), 'bad@example.com');
		await userEvent.type(screen.getByLabelText(/^Name/i), 'Bad User');
		await userEvent.type(getCreatePasswordInput(), 'Secret123!');
		fireEvent.click(screen.getByRole('button', { name: 'Create' }));

		await waitFor(() => {
			expect(screen.getByText('fail')).toBeInTheDocument();
		});
	});
});
