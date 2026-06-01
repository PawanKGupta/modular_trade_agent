import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { LogViewerPage } from '../dashboard/LogViewerPage';

const mockGetUserLogs = vi.fn();
const mockGetAdminLogs = vi.fn();
const mockGetUserErrorLogs = vi.fn();
const mockGetAdminErrorLogs = vi.fn();
const mockResolveErrorLog = vi.fn();
const mockListUsers = vi.fn();

// Mock react-syntax-highlighter to avoid ES module issues in tests
vi.mock('react-syntax-highlighter', () => ({
	Prism: ({ children }: { children: string }) => <pre>{children}</pre>,
	default: ({ children }: { children: string }) => <pre>{children}</pre>,
}));

vi.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
	vscDarkPlus: {},
}));

vi.mock('@/api/logs', () => ({
	getUserLogs: (params: unknown) => mockGetUserLogs(params),
	getAdminLogs: (params: unknown) => mockGetAdminLogs(params),
	getUserErrorLogs: (params: unknown) => mockGetUserErrorLogs(params),
	getAdminErrorLogs: (params: unknown) => mockGetAdminErrorLogs(params),
	resolveErrorLog: (id: number, payload: unknown) => mockResolveErrorLog(id, payload),
}));

vi.mock('@/api/admin', () => ({
	listUsers: (params: unknown) => mockListUsers(params),
}));

const mockUseSessionStore = vi.fn();
vi.mock('@/state/sessionStore', () => ({
	useSessionStore: () => mockUseSessionStore(),
}));

const sampleLogs = [
	{
		id: 1,
		user_id: 1,
		level: 'INFO',
		module: 'scheduler.analysis',
		message: 'Analysis completed',
		context: null,
		timestamp: new Date().toISOString(),
	},
];

const sampleErrors = [
	{
		id: 10,
		user_id: 1,
		error_type: 'ValueError',
		error_message: 'Bad data',
		traceback: 'ValueError: Bad data',
		context: null,
		resolved: false,
		resolved_at: null,
		resolved_by: null,
		resolution_notes: null,
		occurred_at: new Date().toISOString(),
	},
];

function renderPage() {
	const queryClient = new QueryClient();
	return render(
		<QueryClientProvider client={queryClient}>
			<LogViewerPage />
		</QueryClientProvider>
	);
}

beforeEach(() => {
	mockGetUserLogs.mockResolvedValue(sampleLogs);
	mockGetAdminLogs.mockResolvedValue(sampleLogs);
	mockGetUserErrorLogs.mockResolvedValue(sampleErrors);
	mockGetAdminErrorLogs.mockResolvedValue(sampleErrors);
	mockResolveErrorLog.mockResolvedValue({
		message: 'ok',
		error: { ...sampleErrors[0], resolved: true },
	});
	mockListUsers.mockResolvedValue([
		{ id: 1, email: 'admin@example.com', name: 'Admin', role: 'admin', is_active: true, created_at: '', updated_at: '' },
		{ id: 2, email: 'user2@example.com', name: 'User 2', role: 'user', is_active: true, created_at: '', updated_at: '' },
	]);
	mockUseSessionStore.mockReturnValue({
		user: { id: 1, email: 'test@example.com' },
		isAdmin: true,
	});
});

afterEach(() => {
	vi.clearAllMocks();
});

it('renders service and error logs', async () => {
	renderPage();

	await waitFor(() => {
		expect(screen.getByText(/Analysis completed/i)).toBeInTheDocument();
	});
	expect(screen.getByText(/Bad data/i)).toBeInTheDocument();
});

it('switches to admin scope and filters by user id', async () => {
	renderPage();
	const scopeSelect = screen.getByLabelText(/Scope/i);
	await userEvent.selectOptions(scopeSelect, 'all');

	// Wait for UserAutocomplete to load and show users
	await waitFor(() => {
		const userInput = screen.getByPlaceholderText(/Any/i);
		expect(userInput).toBeInTheDocument();
	});

	// UserAutocomplete only searches after at least one character (debounced); clicking alone shows a hint, not the list
	const userInput = screen.getByPlaceholderText(/Any/i);
	await userEvent.click(userInput);
	await userEvent.type(userInput, '2');

	// Wait for debounced search + listUsers, then dropdown with users
	await waitFor(() => {
		expect(screen.getByText(/User 2/i)).toBeInTheDocument();
	});

	// Click on User 2 to select them
	const user2Button = screen.getByText(/User 2/i).closest('button');
	expect(user2Button).toBeInTheDocument();
	await userEvent.click(user2Button!);

	await waitFor(() => {
		expect(mockGetAdminLogs).toHaveBeenCalledWith(
			expect.objectContaining({ user_id: 2 })
		);
	});
});

it('allows admin to resolve errors', async () => {
	const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('fixed');
	renderPage();

	// Switch to admin scope to show resolve button
	const scopeSelect = screen.getByLabelText(/Scope/i);
	await userEvent.selectOptions(scopeSelect, 'all');

	const resolveButton = await screen.findByRole('button', { name: /resolve/i });
	await userEvent.click(resolveButton);

	await waitFor(() => {
		expect(mockResolveErrorLog).toHaveBeenCalledWith(10, { notes: 'fixed' });
	});
	promptSpy.mockRestore();
});

it('falls back to user endpoints when not admin', async () => {
	mockUseSessionStore.mockReturnValue({
		user: { id: 1, email: 'test@example.com' },
		isAdmin: false,
	});
	renderPage();

	await waitFor(() => {
		expect(mockGetUserLogs).toHaveBeenCalled();
		expect(mockGetUserErrorLogs).toHaveBeenCalled();
	});
	expect(mockGetAdminLogs).not.toHaveBeenCalled();
	expect(mockGetAdminErrorLogs).not.toHaveBeenCalled();
});

it('toggles live tail mode and applies log filters', async () => {
	renderPage();
	await waitFor(() => expect(screen.getByText(/Analysis completed/i)).toBeInTheDocument());

	await userEvent.click(screen.getByText('○ Off'));
	expect(screen.getByText(/Live tail mode active/i)).toBeInTheDocument();

	await userEvent.selectOptions(screen.getByLabelText(/^Level$/i), 'ERROR');
	await waitFor(() => {
		expect(mockGetUserLogs).toHaveBeenCalledWith(expect.objectContaining({ level: 'ERROR' }));
	});

	const searchInput = screen.getByPlaceholderText('keyword');
	await userEvent.type(searchInput, 'scheduler');
	await waitFor(() => {
		expect(mockGetUserLogs).toHaveBeenCalledWith(expect.objectContaining({ search: 'scheduler' }));
	});

	await userEvent.click(screen.getAllByRole('checkbox').find(
		(el) => el.closest('label')?.textContent?.includes('Search in context')
	)!);
	await userEvent.click(screen.getAllByRole('checkbox').find(
		(el) => el.closest('label')?.textContent?.includes('Show Log IDs')
	)!);
});

it('applies quick filters, days back, and clears filters', async () => {
	renderPage();
	await waitFor(() => expect(screen.getByText(/Analysis completed/i)).toBeInTheDocument());

	await userEvent.click(screen.getByRole('button', { name: 'Errors Only' }));
	await waitFor(() => {
		expect(mockGetUserLogs).toHaveBeenCalledWith(expect.objectContaining({ level: 'ERROR' }));
	});

	await userEvent.click(screen.getByRole('button', { name: 'This Week' }));
	await waitFor(() => {
		expect(mockGetUserLogs).toHaveBeenCalledWith(expect.objectContaining({ days_back: 7 }));
	});

	const daysBackSelect = screen.getByLabelText(/Days Back/i);
	await userEvent.selectOptions(daysBackSelect, '3');
	await waitFor(() => {
		expect(mockGetUserLogs).toHaveBeenCalledWith(expect.objectContaining({ days_back: 3 }));
	});

	await userEvent.click(screen.getByRole('button', { name: 'Clear Filters' }));
});

it('uses custom log date range when days back is cleared', async () => {
	renderPage();
	await waitFor(() => expect(screen.getByText(/Analysis completed/i)).toBeInTheDocument());

	const daysBackSelect = screen.getByLabelText(/Days Back/i);
	await userEvent.selectOptions(daysBackSelect, '');

	const startInputs = screen.getAllByLabelText(/Start Date/i);
	const endInputs = screen.getAllByLabelText(/End Date/i);
	await userEvent.type(startInputs[0], '2025-01-01');
	await userEvent.type(endInputs[0], '2025-01-31');

	await waitFor(() => {
		expect(mockGetUserLogs).toHaveBeenCalledWith(
			expect.objectContaining({
				start_time: expect.stringContaining('2025-01-01'),
				end_time: expect.stringContaining('2025-01-31'),
				days_back: undefined,
			})
		);
	});
});

it('filters error logs by status, search, and date range', async () => {
	renderPage();
	await waitFor(() => expect(screen.getByText(/Bad data/i)).toBeInTheDocument());

	const statusSelect = screen.getAllByRole('combobox').find(
		(el) => el.closest('label')?.textContent?.includes('Status')
	);
	expect(statusSelect).toBeTruthy();
	await userEvent.selectOptions(statusSelect!, 'false');
	await waitFor(() => {
		expect(mockGetUserErrorLogs).toHaveBeenCalledWith(expect.objectContaining({ resolved: false }));
	});

	const errorSearch = screen.getByPlaceholderText('message contains...');
	await userEvent.type(errorSearch, 'Bad');
	await waitFor(() => {
		expect(mockGetUserErrorLogs).toHaveBeenCalledWith(expect.objectContaining({ search: 'Bad' }));
	});

	const startDateInputs = screen.getAllByLabelText(/Start Date/i);
	const errorStart = startDateInputs[startDateInputs.length - 1];
	await userEvent.type(errorStart, '2025-01-01');
});

it('filters resolved errors and cancels resolve prompt', async () => {
	const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue(null);
	renderPage();
	await waitFor(() => expect(screen.getByText(/Bad data/i)).toBeInTheDocument());

	await userEvent.selectOptions(screen.getAllByLabelText(/^Status$/i)[0], 'true');
	await waitFor(() => {
		expect(mockGetUserErrorLogs).toHaveBeenCalledWith(expect.objectContaining({ resolved: true }));
	});

	await userEvent.selectOptions(screen.getByLabelText(/Scope/i), 'all');
	const resolveButton = await screen.findByRole('button', { name: /resolve/i });
	await userEvent.click(resolveButton);
	expect(mockResolveErrorLog).toHaveBeenCalledWith(10, { notes: undefined });
	promptSpy.mockRestore();
});

it('updates error log limit and date filters', async () => {
	renderPage();
	await waitFor(() => expect(screen.getByText(/Bad data/i)).toBeInTheDocument());

	const limitInput = screen.getByDisplayValue('100');
	await userEvent.clear(limitInput);
	await userEvent.type(limitInput, '50');
	await waitFor(() => {
		expect(mockGetUserErrorLogs).toHaveBeenCalledWith(expect.objectContaining({ limit: 50 }));
	});

	const startDateInputs = screen.getAllByLabelText(/Start Date/i);
	const endDateInputs = screen.getAllByLabelText(/End Date/i);
	await userEvent.type(startDateInputs[startDateInputs.length - 1], '2025-02-01');
	await userEvent.type(endDateInputs[endDateInputs.length - 1], '2025-02-15');
	await waitFor(() => {
		expect(mockGetUserErrorLogs).toHaveBeenCalledWith(
			expect.objectContaining({
				start_time: expect.stringContaining('2025-02-01'),
				end_time: expect.stringContaining('2025-02-15'),
			})
		);
	});
});

it('pauses live tail when scrolled up', async () => {
	renderPage();
	await waitFor(() => expect(screen.getByText(/Analysis completed/i)).toBeInTheDocument());

	await userEvent.click(screen.getByText('○ Off'));
	const container = document.querySelector('.max-h-\\[600px\\]') as HTMLElement;
	expect(container).toBeTruthy();

	Object.defineProperty(container!, 'scrollHeight', { value: 1000, configurable: true });
	Object.defineProperty(container!, 'clientHeight', { value: 400, configurable: true });
	fireEvent.scroll(container!, { target: { scrollTop: 100 } });
	fireEvent.scroll(container!, { target: { scrollTop: 50 } });

	expect(screen.getByText(/Live tail paused/i)).toBeInTheDocument();
});
