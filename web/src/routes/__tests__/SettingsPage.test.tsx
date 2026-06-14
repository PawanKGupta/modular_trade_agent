import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SettingsPage } from '../dashboard/SettingsPage';
import { withProviders } from '@/test/utils';
import { useSessionStore } from '@/state/sessionStore';
import { server } from '@/mocks/server';
import { http, HttpResponse } from 'msw';
import { vi } from 'vitest';

vi.mock('qrcode', () => ({
	default: {
		toDataURL: vi.fn().mockResolvedValue('data:image/png;base64,mockqr'),
	},
}));

describe('SettingsPage', () => {
	beforeEach(() => {
		useSessionStore.setState({
			user: {
				id: 1,
				email: 'test@example.com',
				name: 'Test User',
				mobile_number: null,
				roles: ['user'],
				email_verified: true,
			},
			isAuthenticated: true,
			isAdmin: false,
			hasHydrated: true,
		});
	});
	const renderPage = () =>
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/settings']}>
					<SettingsPage />
				</MemoryRouter>
			)
		);

	const switchToBroker = async (options?: { showFull?: boolean }) => {
		await screen.findByText(/Trading mode/i);
		const brokerRadio = screen.getByLabelText(/Kotak Neo/i);
		fireEvent.click(brokerRadio);

		if (options?.showFull) {
			const toggleButtons = await screen.findAllByRole('button', { name: /Full Credentials/i });
			fireEvent.click(toggleButtons[0]);
			await screen.findByRole('button', { name: /Hide Full Credentials/i });
		}
	};

	it('shows account profile with read-only name and saves mobile', async () => {
		renderPage();
		await screen.findByText(/Account profile/i);
		const nameInput = screen.getByLabelText(/^Name$/i) as HTMLInputElement;
		expect(nameInput.value).toBe('Test User');
		expect(nameInput).toBeDisabled();

		const profileMobile = screen.getByPlaceholderText('10-digit mobile (optional)');
		fireEvent.change(profileMobile, { target: { value: '9876543210' } });
		fireEvent.click(screen.getByRole('button', { name: /Save profile/i }));

		await waitFor(() => {
			expect(screen.getByText(/Profile updated successfully/i)).toBeInTheDocument();
		});
	});

	it('shows validation error for invalid mobile', async () => {
		renderPage();
		await screen.findByText(/Account profile/i);

		fireEvent.change(screen.getByPlaceholderText('10-digit mobile (optional)'), {
			target: { value: '123' },
		});
		fireEvent.click(screen.getByRole('button', { name: /Save profile/i }));

		await waitFor(() => {
			expect(screen.getByText(/10-digit/i)).toBeInTheDocument();
		});
	});

	it('shows profile current password field when email is edited', async () => {
		renderPage();
		await screen.findByText(/Account profile/i);
		expect(document.getElementById('profileCurrentPassword')).not.toBeInTheDocument();

		fireEvent.change(screen.getByLabelText(/^Email$/i), { target: { value: 'new@example.com' } });

		expect(document.getElementById('profileCurrentPassword')).toBeInTheDocument();
	});

	it('requires current password when changing email', async () => {
		renderPage();
		await screen.findByText(/Account profile/i);

		fireEvent.change(screen.getByLabelText(/^Email$/i), { target: { value: 'new@example.com' } });
		fireEvent.click(screen.getByRole('button', { name: /Save profile/i }));

		await waitFor(() => {
			expect(screen.getByText('Current password is required to change email')).toBeInTheDocument();
		});
	});

	it('loads default Paper and saves Broker', async () => {
		renderPage();
		await screen.findByText(/Trading mode/i);
		// default paper checked
		const paper = screen.getByRole('radio', { name: /Paper Trade/i }) as HTMLInputElement;
		expect(paper.checked).toBe(true);
		// switch to broker
		const brokerRadio = screen.getByRole('radio', { name: /Kotak Neo/i });
		fireEvent.click(brokerRadio);
		const brokerInput = await screen.findByPlaceholderText(/kotak-neo/i);
		fireEvent.change(brokerInput, { target: { value: 'kotak-neo' } });
		const save = screen.getByRole('button', { name: /save trading settings/i });
		fireEvent.click(save);
		await waitFor(() => expect(save).toHaveTextContent(/save trading settings/i));
	});

	it('shows broker credentials section when broker mode is selected', async () => {
		renderPage();
		await switchToBroker();

		// Should show broker credentials section
		await waitFor(() => {
			expect(screen.getByText(/API credentials/i)).toBeInTheDocument();
			expect(screen.getByText(/App Token \(API Key\)/i)).toBeInTheDocument();
			expect(screen.getByText(/Client ID \(UCC\)/i)).toBeInTheDocument();
			expect(screen.getByText(/Required for REST Login/i)).toBeInTheDocument();
		});
	});

	it('allows saving broker credentials', async () => {
		renderPage();
		await switchToBroker({ showFull: true });

		const apiKeyInput = await screen.findByPlaceholderText(/Enter App Token/i);
		const apiSecretInput = screen.getByPlaceholderText(/Enter Client ID \(UCC\)/i);

		fireEvent.change(apiKeyInput, { target: { value: 'test-api-key' } });
		fireEvent.change(apiSecretInput, { target: { value: 'test-api-secret' } });

		// Save credentials
		const saveCredsBtn = screen.getByRole('button', { name: /Update Credentials/i });
		fireEvent.click(saveCredsBtn);

		await waitFor(() => {
			expect(screen.getByText(/Credentials saved/i)).toBeInTheDocument();
		});
	});

	it('shows stored credentials indicator when credentials exist', async () => {
		renderPage();
		await switchToBroker();

		// Should show "Show Full Credentials" button if credentials are stored
		await waitFor(() => {
			const showBtns = screen.getAllByRole('button', { name: /Show Full Credentials/i });
			expect(showBtns.length).toBeGreaterThan(0);
			expect(screen.getByText(/Credentials stored/i)).toBeInTheDocument();
		});
	});

	it('allows testing basic connection', async () => {
		renderPage();
		await switchToBroker({ showFull: true });

		const apiKeyInput = await screen.findByPlaceholderText(/Enter App Token/i);
		const apiSecretInput = screen.getByPlaceholderText(/Enter Client ID \(UCC\)/i);

		fireEvent.change(apiKeyInput, { target: { value: 'test-key' } });
		fireEvent.change(apiSecretInput, { target: { value: 'test-secret' } });

		// Select basic test mode
		const basicTestRadio = screen.getByRole('radio', { name: /Basic \(API Key/i });
		fireEvent.click(basicTestRadio);

		// Test connection
		const testBtn = screen.getByRole('button', { name: /Test Basic Connection/i });
		fireEvent.click(testBtn);

		await waitFor(() => {
			expect(screen.getByText(/Client initialized successfully/i)).toBeInTheDocument();
		}, { timeout: 10000 });
	});

	it('allows testing full connection', async () => {
		renderPage();
		await switchToBroker({ showFull: true });

		const apiKeyInput = await screen.findByPlaceholderText(/Enter App Token/i);
		const apiSecretInput = screen.getByPlaceholderText(/Enter Client ID \(UCC\)/i);

		fireEvent.change(apiKeyInput, { target: { value: 'test-key' } });
		fireEvent.change(apiSecretInput, { target: { value: 'test-secret' } });

		// Select full test mode
		const fullTestRadio = screen.getByRole('radio', { name: /Full \(REST/i });
		fireEvent.click(fullTestRadio);

		const mobileInput = await screen.findByPlaceholderText(/Enter mobile number/i);
		const mpinInput = screen.getByPlaceholderText(/Enter MPIN/i);
		const totpInput = screen.getByPlaceholderText(/Enter TOTP Secret/i);

		fireEvent.change(mobileInput, { target: { value: '9876543210' } });
		fireEvent.change(mpinInput, { target: { value: '1234' } });
		fireEvent.change(totpInput, { target: { value: 'BASE32SECRET3232' } });

		// Test connection
		const testBtn = screen.getByRole('button', { name: /Test Full Connection/i });
		fireEvent.click(testBtn);

		await waitFor(() => {
			expect(screen.getByText(/Connection successful/i)).toBeInTheDocument();
		}, { timeout: 10000 });
	});

	it('allows setting up MFA and displaying QR code', async () => {
		const setupMock = vi.fn().mockResolvedValue({
			provisioning_uri: 'otpauth://totp/Rebound:test@example.com?secret=MOCKSECRET&issuer=Rebound',
			secret: 'MOCKSECRET',
			backup_codes: ['code1', 'code2'],
		});
		const verifyMock = vi.fn().mockResolvedValue({ message: 'Verified' });

		server.use(
			http.post('http://localhost:8000/api/v1/auth/mfa/setup', async () => {
				await setupMock();
				return HttpResponse.json({
					provisioning_uri: 'otpauth://totp/Rebound:test@example.com?secret=MOCKSECRET&issuer=Rebound',
					secret: 'MOCKSECRET',
					backup_codes: ['code1', 'code2'],
				});
			}),
			http.post('http://localhost:8000/api/v1/auth/mfa/verify', async ({ request }) => {
				const body = await request.json() as { code: string };
				await verifyMock(body.code);
				return HttpResponse.json({ message: 'MFA enabled successfully.' });
			}),
		);

		renderPage();

		// Open security section
		const securityHeader = await screen.findByText(/Security & two-factor auth/i);
		fireEvent.click(securityHeader);

		// Click set up MFA
		const setupBtn = await screen.findByRole('button', { name: /Set up MFA/i });
		fireEvent.click(setupBtn);

		// Wait for QR code image and secret to be displayed
		const qrCode = await screen.findByAltText(/MFA QR code/i);
		expect(qrCode).toBeInTheDocument();
		expect(screen.getByText('MOCKSECRET')).toBeInTheDocument();
		expect(screen.getByText(/code1\s+code2/i)).toBeInTheDocument();

		// Enter 6-digit confirmation code
		const confirmInput = screen.getByLabelText(/Enter the 6-digit code to confirm/i);
		fireEvent.change(confirmInput, { target: { value: '123456' } });

		const confirmBtn = screen.getByRole('button', { name: /Confirm & Enable MFA/i });
		fireEvent.click(confirmBtn);

		// Verification mock should be called with correct code
		await waitFor(() => {
			expect(verifyMock).toHaveBeenCalledWith('123456');
			expect(screen.getByText(/MFA enabled successfully/i)).toBeInTheDocument();
		});
	});

	it('allows disabling MFA when enabled', async () => {
		// Mock user with MFA enabled
		useSessionStore.setState({
			user: {
				id: 1,
				email: 'test@example.com',
				name: 'Test User',
				mobile_number: null,
				roles: ['user'],
				email_verified: true,
				mfa_enabled: true,
			},
			isAuthenticated: true,
			isAdmin: false,
			hasHydrated: true,
		});

		const disableMock = vi.fn().mockResolvedValue({ message: 'Disabled' });

		server.use(
			http.post('http://localhost:8000/api/v1/auth/mfa/disable', async ({ request }) => {
				const body = await request.json() as { current_password?: string; code?: string };
				await disableMock(body.current_password, body.code);
				return HttpResponse.json({ message: 'MFA disabled.' });
			}),
		);

		renderPage();

		// Open security section
		const securityHeader = await screen.findByText(/Security & two-factor auth/i);
		fireEvent.click(securityHeader);

		// Verify we see MFA is active message
		await screen.findByText(/MFA is active on your account/i);

		const passwordInput = screen.getByPlaceholderText('Current password');
		const codeInput = screen.getByPlaceholderText('6-digit authenticator or backup code');

		fireEvent.change(passwordInput, { target: { value: 'Secret123!' } });
		fireEvent.change(codeInput, { target: { value: '123456' } });

		const disableBtn = screen.getByRole('button', { name: /Disable MFA/i });
		fireEvent.click(disableBtn);

		await waitFor(() => {
			expect(disableMock).toHaveBeenCalledWith('Secret123!', '123456');
			expect(screen.getByText(/MFA disabled/i)).toBeInTheDocument();
		});
	});
});
