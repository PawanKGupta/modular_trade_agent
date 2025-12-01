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

vi.mock('@/api/logs', () => ({
	getUserLogs: (params: unknown) => mockGetUserLogs(params),
	getAdminLogs: (params: unknown) => mockGetAdminLogs(params),
	getUserErrorLogs: (params: unknown) => mockGetUserErrorLogs(params),
	getAdminErrorLogs: (params: unknown) => mockGetAdminErrorLogs(params),
	resolveErrorLog: (id: number, payload: unknown) => mockResolveErrorLog(id, payload),
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
	const userIdInput = screen.getByLabelText(/User ID/i);
	await userEvent.type(userIdInput, '2');

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
