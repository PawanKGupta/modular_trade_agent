import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { NotificationsPage } from '../dashboard/NotificationsPage';
import { withProviders } from '@/test/utils';

const mockNotifications = [
	{
		id: 1,
		user_id: 1,
		type: 'service' as const,
		level: 'info' as const,
		title: 'Service Started',
		message: 'Service: Analysis\nStatus: Running',
		read: false,
		read_at: null,
		created_at: '2025-11-30T10:00:00Z',
		telegram_sent: false,
		email_sent: false,
		in_app_delivered: true,
	},
	{
		id: 2,
		user_id: 1,
		type: 'service' as const,
		level: 'error' as const,
		title: 'Service Execution Failed',
		message: 'Service: Analysis\nStatus: Failed\nError: Test error',
		read: false,
		read_at: null,
		created_at: '2025-11-30T10:05:00Z',
		telegram_sent: false,
		email_sent: false,
		in_app_delivered: true,
	},
	{
		id: 3,
		user_id: 1,
		type: 'trading' as const,
		level: 'info' as const,
		title: 'Order Executed',
		message: 'Order for RELIANCE.NS executed successfully',
		read: true,
		read_at: '2025-11-30T10:10:00Z',
		created_at: '2025-11-30T10:00:00Z',
		telegram_sent: true,
		email_sent: false,
		in_app_delivered: true,
	},
];

// Mock the API
vi.mock('@/api/notifications', () => ({
	getNotifications: vi.fn(() => Promise.resolve(mockNotifications)),
	getUnreadNotifications: vi.fn(() => Promise.resolve(mockNotifications.filter((n) => !n.read))),
	getNotificationCount: vi.fn(() => Promise.resolve({ unread_count: 2 })),
	markNotificationRead: vi.fn((id) => Promise.resolve({ ...mockNotifications.find((n) => n.id === id)!, read: true })),
	markAllNotificationsRead: vi.fn(() => Promise.resolve({ marked_read: 2 })),
}));

describe('NotificationsPage', () => {
	const renderPage = () =>
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/notifications']}>
					<NotificationsPage />
				</MemoryRouter>
			)
		);

	beforeEach(async () => {
		const notificationApi = await import('@/api/notifications');
		vi.mocked(notificationApi.getNotifications).mockResolvedValue(mockNotifications);
		vi.mocked(notificationApi.getUnreadNotifications).mockResolvedValue(
			mockNotifications.filter((n) => !n.read)
		);
		vi.mocked(notificationApi.getNotificationCount).mockResolvedValue({ unread_count: 2 });
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	it('loads and displays notifications', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Notifications/i)).toBeInTheDocument();
		});

		// Check that notifications are rendered
		expect(screen.getByText(/Service Started/i)).toBeInTheDocument();
		expect(screen.getByText(/Service Execution Failed/i)).toBeInTheDocument();
		expect(screen.getByText(/Order Executed/i)).toBeInTheDocument();
	});

	it('shows loading state initially', async () => {
		const notificationApi = await import('@/api/notifications');
		vi.mocked(notificationApi.getNotifications).mockImplementation(
			() => new Promise(() => {}) // Never resolves
		);

		renderPage();
		expect(screen.getByText(/Loading notifications/i)).toBeInTheDocument();
	});

	it('displays unread count in mark all read button', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Mark All Read/i)).toBeInTheDocument();
		});

		expect(screen.getByText(/Mark All Read \(2\)/i)).toBeInTheDocument();
	});

	it('allows filtering by type', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Notifications/i)).toBeInTheDocument();
		});

		const selects = screen.getAllByRole('combobox');
		const typeSelect = selects.find((s) => (s as HTMLSelectElement).options[0]?.textContent === 'All') as HTMLSelectElement;
		expect(typeSelect).toBeInTheDocument();

		fireEvent.change(typeSelect, { target: { value: 'service' } });
		expect(typeSelect.value).toBe('service');
	});

	it('allows filtering by level', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Notifications/i)).toBeInTheDocument();
		});

		const selects = screen.getAllByRole('combobox');
		const levelSelect = selects.find((s) => {
			const options = Array.from((s as HTMLSelectElement).options);
			return options.some((opt) => opt.textContent === 'Info');
		}) as HTMLSelectElement;
		expect(levelSelect).toBeInTheDocument();

		fireEvent.change(levelSelect, { target: { value: 'error' } });
		expect(levelSelect.value).toBe('error');
	});

	it('allows marking individual notification as read', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Service Started/i)).toBeInTheDocument();
		});

		const markReadButtons = screen.getAllByText(/Mark Read/i);
		expect(markReadButtons.length).toBeGreaterThan(0);

		fireEvent.click(markReadButtons[0]);

		await waitFor(async () => {
			const notificationApi = await import('@/api/notifications');
			expect(notificationApi.markNotificationRead).toHaveBeenCalled();
		});
	});

	it('allows marking all notifications as read', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Mark All Read/i)).toBeInTheDocument();
		});

		const markAllReadButton = screen.getByText(/Mark All Read/i);
		fireEvent.click(markAllReadButton);

		await waitFor(async () => {
			const notificationApi = await import('@/api/notifications');
			expect(notificationApi.markAllNotificationsRead).toHaveBeenCalled();
		});
	});

	it('displays notification details correctly', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Service Started/i)).toBeInTheDocument();
		});

		// Check notification content - use getAllByText since there are multiple notifications
		const analysisTexts = screen.getAllByText(/Service: Analysis/i);
		expect(analysisTexts.length).toBeGreaterThan(0);
		expect(screen.getByText(/Status: Running/i)).toBeInTheDocument();
	});

	it('shows "New" badge for unread notifications', async () => {
		renderPage();

		await waitFor(() => {
			const newBadges = screen.queryAllByText(/New/i);
			expect(newBadges.length).toBeGreaterThan(0);
		});

		const newBadges = screen.getAllByText(/New/i);
		expect(newBadges.length).toBe(2); // Two unread notifications
	});

	it('displays empty state when no notifications', async () => {
		const notificationApi = await import('@/api/notifications');
		vi.mocked(notificationApi.getNotifications).mockResolvedValue([]);

		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/No notifications found/i)).toBeInTheDocument();
		});
	});

	it('hides mark all read button when no unread notifications', async () => {
		const notificationApi = await import('@/api/notifications');
		vi.mocked(notificationApi.getNotifications).mockResolvedValue(
			mockNotifications.map((n) => ({ ...n, read: true }))
		);
		vi.mocked(notificationApi.getNotificationCount).mockResolvedValue({ unread_count: 0 });

		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Notifications/i)).toBeInTheDocument();
		});

		expect(screen.queryByText(/Mark All Read/i)).not.toBeInTheDocument();
	});

	it('mark all read button remains visible on hover', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Mark All Read/i)).toBeInTheDocument();
		});

		const markAllReadButton = screen.getByText(/Mark All Read/i);
		expect(markAllReadButton).toBeInTheDocument();

		// Verify button has correct hover styles (opacity-based, not undefined CSS variable)
		expect(markAllReadButton).toHaveClass('hover:opacity-90');
		expect(markAllReadButton).toHaveClass('transition-opacity');

		// Verify button does NOT use undefined --accent-hover variable
		expect(markAllReadButton.className).not.toContain('hover:bg-[var(--accent-hover)]');

		// Simulate hover
		fireEvent.mouseEnter(markAllReadButton);

		// Button should still be visible after hover
		expect(markAllReadButton).toBeInTheDocument();
		expect(markAllReadButton).toBeVisible();
	});
});
