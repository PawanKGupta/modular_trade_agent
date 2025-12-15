import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UserAutocomplete } from '../UserAutocomplete';
import { listUsers } from '@/api/admin';
import type { AdminUser } from '@/api/admin';

// Mock the API
vi.mock('@/api/admin', () => ({
	listUsers: vi.fn(),
}));

const mockUsers: AdminUser[] = [
	{
		id: 1,
		email: 'admin@example.com',
		name: 'Admin User',
		role: 'admin',
		is_active: true,
		created_at: '2024-01-01T00:00:00Z',
		updated_at: '2024-01-01T00:00:00Z',
	},
	{
		id: 2,
		email: 'user@example.com',
		name: 'Regular User',
		role: 'user',
		is_active: true,
		created_at: '2024-01-01T00:00:00Z',
		updated_at: '2024-01-01T00:00:00Z',
	},
	{
		id: 3,
		email: 'john.doe@example.com',
		name: null,
		role: 'user',
		is_active: true,
		created_at: '2024-01-01T00:00:00Z',
		updated_at: '2024-01-01T00:00:00Z',
	},
];

function renderWithQueryClient(component: React.ReactElement) {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
		},
	});
	return render(<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>);
}

describe('UserAutocomplete', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(listUsers).mockResolvedValue(mockUsers);
	});

	it('renders input field with placeholder', () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		expect(input).toBeInTheDocument();
	});

	it('fetches and displays users list', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			expect(listUsers).toHaveBeenCalled();
		});

		await waitFor(() => {
			expect(screen.getByText('Admin User')).toBeInTheDocument();
			expect(screen.getByText('Regular User')).toBeInTheDocument();
		});
	});

	it('filters users by name', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			expect(screen.getByText('Admin User')).toBeInTheDocument();
		});

		fireEvent.change(input, { target: { value: 'Regular' } });

		await waitFor(() => {
			expect(screen.getByText('Regular User')).toBeInTheDocument();
			expect(screen.queryByText('Admin User')).not.toBeInTheDocument();
		});
	});

	it('filters users by email', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			expect(screen.getByText('Admin User')).toBeInTheDocument();
		});

		fireEvent.change(input, { target: { value: 'user@example.com' } });

		await waitFor(() => {
			expect(screen.getByText('Regular User')).toBeInTheDocument();
			expect(screen.queryByText('Admin User')).not.toBeInTheDocument();
		});
	});

	it('filters users by ID', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			expect(screen.getByText('Admin User')).toBeInTheDocument();
		});

		fireEvent.change(input, { target: { value: '1' } });

		await waitFor(() => {
			expect(screen.getByText('Admin User')).toBeInTheDocument();
			expect(screen.queryByText('Regular User')).not.toBeInTheDocument();
		});
	});

	it('selects user when clicked', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			expect(screen.getByText('Admin User')).toBeInTheDocument();
		});

		const userButton = screen.getByText('Admin User').closest('button');
		expect(userButton).toBeInTheDocument();
		fireEvent.click(userButton!);

		expect(onChange).toHaveBeenCalledWith('1');
	});

	it('displays selected user name in input', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="1" onChange={onChange} />);

		await waitFor(() => {
			const input = screen.getByPlaceholderText('Any') as HTMLInputElement;
			expect(input.value).toBe('Admin User');
		});
	});

	it('displays email when user has no name', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="3" onChange={onChange} />);

		await waitFor(() => {
			const input = screen.getByPlaceholderText('Any') as HTMLInputElement;
			expect(input.value).toBe('john.doe@example.com');
		});
	});

	it('shows clear button when user is selected', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="1" onChange={onChange} />);

		await waitFor(() => {
			const clearButton = screen.getByTitle('Clear selection');
			expect(clearButton).toBeInTheDocument();
		});
	});

	it('clears selection when clear button is clicked', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="1" onChange={onChange} />);

		await waitFor(() => {
			const clearButton = screen.getByTitle('Clear selection');
			expect(clearButton).toBeInTheDocument();
		});

		const clearButton = screen.getByTitle('Clear selection');
		fireEvent.click(clearButton);

		expect(onChange).toHaveBeenCalledWith('');
	});

	it('shows loading state', () => {
		vi.mocked(listUsers).mockImplementation(
			() => new Promise(() => {}) // Never resolves
		);

		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		expect(screen.getByText('Loading users...')).toBeInTheDocument();
	});

	it('shows "No users found" when search has no results', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			expect(screen.getByText('Admin User')).toBeInTheDocument();
		});

		fireEvent.change(input, { target: { value: 'nonexistent' } });

		await waitFor(() => {
			expect(screen.getByText('No users found')).toBeInTheDocument();
		});
	});

	it('clears selection when user types different value', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="1" onChange={onChange} />);

		await waitFor(() => {
			const input = screen.getByPlaceholderText('Any') as HTMLInputElement;
			expect(input.value).toBe('Admin User');
		});

		const input = screen.getByPlaceholderText('Any');
		fireEvent.change(input, { target: { value: 'Different' } });

		expect(onChange).toHaveBeenCalledWith('');
	});

	it('displays user email as secondary info when name exists', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			expect(screen.getByText('admin@example.com')).toBeInTheDocument();
		});
	});

	it('displays ID as secondary info when user has no name', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			expect(screen.getByText('ID: 3')).toBeInTheDocument();
		});
	});

	it('limits results to 10 users', async () => {
		const manyUsers: AdminUser[] = Array.from({ length: 15 }, (_, i) => ({
			id: i + 1,
			email: `user${i + 1}@example.com`,
			name: `User ${i + 1}`,
			role: 'user' as const,
			is_active: true,
			created_at: '2024-01-01T00:00:00Z',
			updated_at: '2024-01-01T00:00:00Z',
		}));

		vi.mocked(listUsers).mockResolvedValue(manyUsers);

		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			const buttons = screen.getAllByRole('button').filter((btn) =>
				btn.textContent?.startsWith('User')
			);
			expect(buttons.length).toBeLessThanOrEqual(10);
		});
	});

	it('handles empty users list', async () => {
		vi.mocked(listUsers).mockResolvedValue([]);

		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		await waitFor(() => {
			expect(listUsers).toHaveBeenCalled();
		});

		// Should not crash, dropdown should not appear
		expect(screen.queryByText('Admin User')).not.toBeInTheDocument();
	});
});
