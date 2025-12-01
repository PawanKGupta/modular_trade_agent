import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { NotificationPreferencesPage } from '../dashboard/NotificationPreferencesPage';
import { withProviders } from '@/test/utils';

const mockPreferences = {
	telegram_enabled: false,
	telegram_chat_id: null,
	email_enabled: false,
	email_address: null,
	in_app_enabled: true,
	notify_service_events: true,
	notify_trading_events: true,
	notify_system_events: true,
	notify_errors: true,
	notify_order_placed: true,
	notify_order_rejected: true,
	notify_order_executed: true,
	notify_order_cancelled: true,
	notify_order_modified: false,
	notify_retry_queue_added: true,
	notify_retry_queue_updated: true,
	notify_retry_queue_removed: true,
	notify_retry_queue_retried: true,
	notify_partial_fill: true,
	notify_system_errors: true,
	notify_system_warnings: false,
	notify_system_info: false,
	notify_service_started: true,
	notify_service_stopped: true,
	notify_service_execution_completed: true,
	quiet_hours_start: null,
	quiet_hours_end: null,
};

// Mock the API
vi.mock('@/api/notification-preferences', () => ({
	getNotificationPreferences: vi.fn(() => Promise.resolve(mockPreferences)),
	updateNotificationPreferences: vi.fn(() => Promise.resolve(mockPreferences)),
}));

describe('NotificationPreferencesPage', () => {
	const renderPage = () =>
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/notification-preferences']}>
					<NotificationPreferencesPage />
				</MemoryRouter>
			)
		);

	beforeEach(async () => {
		const notificationApi = await import('@/api/notification-preferences');
		vi.mocked(notificationApi.getNotificationPreferences).mockResolvedValue(mockPreferences);
		vi.mocked(notificationApi.updateNotificationPreferences).mockResolvedValue(mockPreferences);
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	it('loads and displays notification preferences', async () => {
		renderPage();

		// Wait for all sections to be rendered
		await waitFor(() => {
			expect(screen.getByText(/Notification Preferences/i)).toBeInTheDocument();
			expect(screen.getByText(/Notification Channels/i)).toBeInTheDocument();
			expect(screen.getByText(/Order Events/i)).toBeInTheDocument();
			expect(screen.getByText(/Retry Queue Events/i)).toBeInTheDocument();
			expect(screen.getByText(/System Events/i)).toBeInTheDocument();
			expect(screen.getByText(/Service Events/i)).toBeInTheDocument();
			expect(screen.getByText(/Quiet Hours/i)).toBeInTheDocument();
		});
	});

	it('shows loading state initially', async () => {
		const notificationApi = await import('@/api/notification-preferences');
		vi.mocked(notificationApi.getNotificationPreferences).mockImplementation(
			() => new Promise(() => {}) // Never resolves
		);

		renderPage();
		expect(screen.getByText(/Loading notification preferences/i)).toBeInTheDocument();
	});

	it('allows toggling individual preferences', async () => {
		renderPage();

		// Wait for content to load
		await waitFor(() => {
			expect(screen.getByText(/Notification Preferences/i)).toBeInTheDocument();
			expect(screen.getByText(/Order Events/i)).toBeInTheDocument();
		});

		// Toggle a preference - wait for the checkbox to be available
		const orderPlacedCheckbox = await waitFor(() => {
			return screen.getByLabelText(/Order Placed/i) as HTMLInputElement;
		});
		expect(orderPlacedCheckbox.checked).toBe(true);

		fireEvent.click(orderPlacedCheckbox);
		expect(orderPlacedCheckbox.checked).toBe(false);

		// Should show unsaved changes
		expect(screen.getByText(/Unsaved changes/i)).toBeInTheDocument();
	});

	it('shows conditional fields when channels are enabled', async () => {
		renderPage();

		// Wait for content to load
		await waitFor(() => {
			expect(screen.getByText(/Notification Preferences/i)).toBeInTheDocument();
			expect(screen.getByText(/Notification Channels/i)).toBeInTheDocument();
		});

		// Enable Telegram - wait for the checkbox to be available
		const telegramCheckbox = await waitFor(() => {
			return screen.getByLabelText(/Telegram/i) as HTMLInputElement;
		});
		fireEvent.click(telegramCheckbox);

		await waitFor(() => {
			expect(screen.getByPlaceholderText(/Telegram Chat ID/i)).toBeInTheDocument();
		});

		// Enable Email
		const emailCheckbox = screen.getByLabelText(/Email/i) as HTMLInputElement;
		fireEvent.click(emailCheckbox);

		await waitFor(() => {
			expect(screen.getByPlaceholderText(/Email address/i)).toBeInTheDocument();
		});
	});

	it('allows saving preferences', async () => {
		renderPage();

		// Wait for content to load
		await waitFor(() => {
			expect(screen.getByText(/Notification Preferences/i)).toBeInTheDocument();
			expect(screen.getByText(/Order Events/i)).toBeInTheDocument();
		});

		// Make a change - wait for checkbox
		const orderPlacedCheckbox = await waitFor(() => {
			return screen.getByLabelText(/Order Placed/i);
		});
		fireEvent.click(orderPlacedCheckbox);

		// Save - wait for button
		const saveButton = await waitFor(() => {
			return screen.getByRole('button', { name: /Save Preferences/i });
		});
		fireEvent.click(saveButton);

		await waitFor(async () => {
			const notificationApi = await import('@/api/notification-preferences');
			expect(notificationApi.updateNotificationPreferences).toHaveBeenCalled();
			expect(screen.getByText(/saved successfully/i)).toBeInTheDocument();
		});
	});

	it('disables save button when no changes', async () => {
		renderPage();

		// Wait for content to load
		await waitFor(() => {
			expect(screen.getByText(/Notification Preferences/i)).toBeInTheDocument();
		});

		// Wait for save button
		const saveButton = await waitFor(() => {
			return screen.getByRole('button', { name: /Save Preferences/i });
		});
		expect(saveButton).toBeDisabled();
	});

	it('shows error message on save failure', async () => {
		const notificationApi = await import('@/api/notification-preferences');
		vi.mocked(notificationApi.updateNotificationPreferences).mockRejectedValue(
			new Error('Failed to save')
		);

		renderPage();

		// Wait for content to load
		await waitFor(() => {
			expect(screen.getByText(/Notification Preferences/i)).toBeInTheDocument();
			expect(screen.getByText(/Order Events/i)).toBeInTheDocument();
		});

		// Make a change - wait for checkbox
		const orderPlacedCheckbox = await waitFor(() => {
			return screen.getByLabelText(/Order Placed/i);
		});
		fireEvent.click(orderPlacedCheckbox);

		// Save - wait for button
		const saveButton = await waitFor(() => {
			return screen.getByRole('button', { name: /Save Preferences/i });
		});
		fireEvent.click(saveButton);

		await waitFor(() => {
			expect(screen.getByText(/Failed to save/i)).toBeInTheDocument();
		});
	});

	it('allows enabling all order events', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Order Events/i)).toBeInTheDocument();
		});

		const enableAllButton = screen.getAllByRole('button', { name: /Enable All/i })[0];
		fireEvent.click(enableAllButton);

		// All order event checkboxes should be checked
		await waitFor(() => {
			const orderPlaced = screen.getByLabelText(/Order Placed/i) as HTMLInputElement;
			const orderExecuted = screen.getByLabelText(/Order Executed/i) as HTMLInputElement;
			expect(orderPlaced.checked).toBe(true);
			expect(orderExecuted.checked).toBe(true);
		});
	});

	it('allows setting quiet hours', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Quiet Hours/i)).toBeInTheDocument();
		});

		// Wait for time inputs - find by their parent label text since labels aren't properly associated
		await waitFor(() => {
			expect(screen.getByText(/Start Time/i)).toBeInTheDocument();
			expect(screen.getByText(/End Time/i)).toBeInTheDocument();
		});

		// Find inputs by searching near the label text
		const quietHoursSection = screen.getByText(/Quiet Hours/i).closest('section');
		const timeInputs = quietHoursSection?.querySelectorAll('input[type="time"]') as NodeListOf<HTMLInputElement>;
		expect(timeInputs?.length).toBeGreaterThanOrEqual(2);

		const startTimeInput = timeInputs[0];
		const endTimeInput = timeInputs[1];

		fireEvent.change(startTimeInput, { target: { value: '22:00' } });
		fireEvent.change(endTimeInput, { target: { value: '08:00' } });

		expect(startTimeInput.value).toBe('22:00');
		expect(endTimeInput.value).toBe('08:00');
	});

	it('allows clearing quiet hours', async () => {
		const prefsWithQuietHours = {
			...mockPreferences,
			quiet_hours_start: '22:00:00',
			quiet_hours_end: '08:00:00',
		};
		const notificationApi = await import('@/api/notification-preferences');
		vi.mocked(notificationApi.getNotificationPreferences).mockResolvedValue(prefsWithQuietHours);

		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Quiet Hours/i)).toBeInTheDocument();
		});

		const clearButton = await waitFor(() => {
			return screen.getByRole('button', { name: /Clear/i });
		});

		// Find the inputs before clearing to verify they have values
		const quietHoursSection = screen.getByText(/Quiet Hours/i).closest('section');
		const timeInputsBefore = quietHoursSection?.querySelectorAll('input[type="time"]') as NodeListOf<HTMLInputElement>;
		expect(timeInputsBefore?.length).toBeGreaterThanOrEqual(2);
		expect(timeInputsBefore[0].value).toBe('22:00');
		expect(timeInputsBefore[1].value).toBe('08:00');

		fireEvent.click(clearButton);

		// Verify that clicking Clear triggers a state change (shows unsaved changes)
		await waitFor(() => {
			expect(screen.getByText(/Unsaved changes/i)).toBeInTheDocument();
		});

		// Verify that the save button is now enabled (indicating changes were made)
		const saveButton = await waitFor(() => {
			const btn = screen.getByRole('button', { name: /Save Preferences/i });
			expect(btn).not.toBeDisabled();
			return btn;
		});
	});

	it('allows toggling service event preferences', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Service Events/i)).toBeInTheDocument();
		});

		// Toggle service started
		const serviceStartedCheckbox = screen.getByLabelText(/Service Started/i) as HTMLInputElement;
		expect(serviceStartedCheckbox.checked).toBe(true);
		fireEvent.click(serviceStartedCheckbox);
		expect(serviceStartedCheckbox.checked).toBe(false);

		// Toggle service stopped
		const serviceStoppedCheckbox = screen.getByLabelText(/Service Stopped/i) as HTMLInputElement;
		expect(serviceStoppedCheckbox.checked).toBe(true);
		fireEvent.click(serviceStoppedCheckbox);
		expect(serviceStoppedCheckbox.checked).toBe(false);

		// Toggle service execution completed
		const serviceExecutionCheckbox = screen.getByLabelText(/Service Execution Completed/i) as HTMLInputElement;
		expect(serviceExecutionCheckbox.checked).toBe(true);
		fireEvent.click(serviceExecutionCheckbox);
		expect(serviceExecutionCheckbox.checked).toBe(false);

		// Should show unsaved changes
		expect(screen.getByText(/Unsaved changes/i)).toBeInTheDocument();
	});

	it('allows enabling all service events', async () => {
		renderPage();

		await waitFor(() => {
			expect(screen.getByText(/Service Events/i)).toBeInTheDocument();
		});

		// Find the Enable All button for Service Events section
		const enableAllButtons = screen.getAllByRole('button', { name: /Enable All/i });
		// Service Events section should have Enable All button (it's the 4th section)
		const serviceEnableAllButton = enableAllButtons[3];
		fireEvent.click(serviceEnableAllButton);

		// All service event checkboxes should be checked
		await waitFor(() => {
			const serviceStarted = screen.getByLabelText(/Service Started/i) as HTMLInputElement;
			const serviceStopped = screen.getByLabelText(/Service Stopped/i) as HTMLInputElement;
			const serviceExecution = screen.getByLabelText(/Service Execution Completed/i) as HTMLInputElement;
			expect(serviceStarted.checked).toBe(true);
			expect(serviceStopped.checked).toBe(true);
			expect(serviceExecution.checked).toBe(true);
		});
	});
});
