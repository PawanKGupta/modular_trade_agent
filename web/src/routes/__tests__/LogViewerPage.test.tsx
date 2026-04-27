import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
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
