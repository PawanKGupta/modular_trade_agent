import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UserAutocomplete } from '../UserAutocomplete';
import { listUsers } from '@/api/admin';
import type { AdminUser } from '@/api/admin';

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

function mockListByQuery(params?: { q?: string; limit?: number }) {
	const q = params?.q?.toLowerCase() ?? '';
	if (!q) return Promise.resolve(mockUsers);
	return Promise.resolve(
		mockUsers.filter(
			(u) =>
				u.id.toString().includes(q) ||
				u.email?.toLowerCase().includes(q) ||
				(u.name && u.name.toLowerCase().includes(q))
		)
	);
}

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
		vi.mocked(listUsers).mockImplementation(mockListByQuery);
	});

	it('renders input field with placeholder', () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		expect(screen.getByPlaceholderText('Any')).toBeInTheDocument();
	});

	it('searches after debounce and displays results', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: 'a' } });

		await waitFor(
			() => {
				expect(listUsers).toHaveBeenCalledWith({ q: 'a', limit: 40 });
			},
			{ timeout: 4000 }
		);

		expect(screen.getByText('Admin User')).toBeInTheDocument();
	});

	it('filters users by name via server', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: 'Regular' } });

		await waitFor(
			() => {
				expect(screen.getByText('Regular User')).toBeInTheDocument();
				expect(screen.queryByText('Admin User')).not.toBeInTheDocument();
			},
			{ timeout: 4000 }
		);
	});

	it('filters users by email via server', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: 'user@example.com' } });

		await waitFor(
			() => {
				expect(screen.getByText('Regular User')).toBeInTheDocument();
				expect(screen.queryByText('Admin User')).not.toBeInTheDocument();
			},
			{ timeout: 4000 }
		);
	});

	it('filters users by ID via server', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: '1' } });

		await waitFor(
			() => {
				expect(screen.getByText('Admin User')).toBeInTheDocument();
				expect(screen.queryByText('Regular User')).not.toBeInTheDocument();
			},
			{ timeout: 4000 }
		);
	});

	it('selects user when clicked', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: 'admin' } });

		await waitFor(() => expect(screen.getByText('Admin User')).toBeInTheDocument(), { timeout: 4000 });

		const userButton = screen.getByText('Admin User').closest('button');
		expect(userButton).toBeInTheDocument();
		fireEvent.click(userButton!);

		expect(onChange).toHaveBeenCalledWith('1');
	});

	it('displays selected user name in input', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="1" onChange={onChange} placeholder="Any" />);

		await waitFor(
			() => {
				const el = screen.getByPlaceholderText('Any') as HTMLInputElement;
				expect(el.value).toBe('Admin User');
			},
			{ timeout: 4000 }
		);
	});

	it('displays email when user has no name', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="3" onChange={onChange} placeholder="Any" />);

		await waitFor(
			() => {
				const el = screen.getByPlaceholderText('Any') as HTMLInputElement;
				expect(el.value).toBe('john.doe@example.com');
			},
			{ timeout: 4000 }
		);
	});

	it('shows clear button when user is selected', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="1" onChange={onChange} placeholder="Any" />);

		await waitFor(() => expect(screen.getByTitle('Clear selection')).toBeInTheDocument(), { timeout: 4000 });
	});

	it('clears selection when clear button is clicked', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="1" onChange={onChange} placeholder="Any" />);

		await waitFor(() => expect(screen.getByTitle('Clear selection')).toBeInTheDocument(), { timeout: 4000 });

		fireEvent.click(screen.getByTitle('Clear selection'));

		expect(onChange).toHaveBeenCalledWith('');
	});

	it('shows searching state while request in flight', async () => {
		vi.mocked(listUsers).mockImplementation(
			() => new Promise(() => {}) // never resolves
		);

		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: 'x' } });

		await waitFor(() => expect(screen.getByText('Searching…')).toBeInTheDocument(), { timeout: 4000 });
	});

	it('shows "No users found" when search has no results', async () => {
		vi.mocked(listUsers).mockResolvedValue([]);

		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: 'nonexistent' } });

		await waitFor(() => expect(screen.getByText('No users found')).toBeInTheDocument(), { timeout: 4000 });
	});

	it('clears selection when user types different value', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="1" onChange={onChange} placeholder="Any" />);

		await waitFor(
			() => {
				const el = screen.getByPlaceholderText('Any') as HTMLInputElement;
				expect(el.value).toBe('Admin User');
			},
			{ timeout: 4000 }
		);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.change(input, { target: { value: 'Different' } });

		expect(onChange).toHaveBeenCalledWith('');
	});

	it('displays user email as secondary info when name exists', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: 'admin' } });

		await waitFor(() => expect(screen.getByText('admin@example.com')).toBeInTheDocument(), { timeout: 4000 });
	});

	it('displays ID as secondary info when user has no name', async () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: 'john' } });

		await waitFor(() => expect(screen.getByText('ID: 3')).toBeInTheDocument(), { timeout: 4000 });
	});

	it('shows hint before typing', () => {
		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);

		expect(screen.getByText(/Type at least one character/)).toBeInTheDocument();
		expect(listUsers).not.toHaveBeenCalled();
	});

	it('handles empty users list from server', async () => {
		vi.mocked(listUsers).mockResolvedValue([]);

		const onChange = vi.fn();
		renderWithQueryClient(<UserAutocomplete value="" onChange={onChange} placeholder="Any" />);

		const input = screen.getByPlaceholderText('Any');
		fireEvent.focus(input);
		fireEvent.change(input, { target: { value: 'z' } });

		await waitFor(() => expect(listUsers).toHaveBeenCalled(), { timeout: 4000 });

		expect(screen.getByText('No users found')).toBeInTheDocument();
	});
});
