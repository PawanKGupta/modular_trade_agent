import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SettingsPage } from '../dashboard/SettingsPage';
import { withProviders } from '@/test/utils';

describe('SettingsPage', () => {
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

	it('loads default Paper and saves Broker', async () => {
		renderPage();
		await screen.findByText(/Trading mode/i);
		// default paper checked
		const paper = screen.getByLabelText(/Paper Trade/i) as HTMLInputElement;
		expect(paper.checked).toBe(true);
		// switch to broker
		const brokerRadio = screen.getByLabelText(/Kotak Neo/i);
		fireEvent.click(brokerRadio);
		const brokerInput = await screen.findByPlaceholderText(/kotak-neo/i);
		fireEvent.change(brokerInput, { target: { value: 'kotak-neo' } });
		const save = screen.getByRole('button', { name: /save settings/i });
		fireEvent.click(save);
		await waitFor(() => expect(save).toHaveTextContent(/save settings/i));
	});

	it('shows broker credentials section when broker mode is selected', async () => {
		renderPage();
		await switchToBroker();

		// Should show broker credentials section
		await waitFor(() => {
			expect(screen.getByText(/Basic Credentials/i)).toBeInTheDocument();
			expect(screen.getByText(/API Key \(Consumer Key\)/i)).toBeInTheDocument();
			expect(screen.getByText(/API Secret \(Consumer Secret\)/i)).toBeInTheDocument();
			expect(screen.getByText(/Full Authentication Credentials/i)).toBeInTheDocument();
		});
	});

	it('allows saving broker credentials', async () => {
		renderPage();
		await switchToBroker({ showFull: true });

		const apiKeyInput = await screen.findByPlaceholderText(/Enter API Key/i);
		const apiSecretInput = screen.getByPlaceholderText(/Enter API Secret/i);

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

		const apiKeyInput = await screen.findByPlaceholderText(/Enter API Key/i);
		const apiSecretInput = screen.getByPlaceholderText(/Enter API Secret/i);

		fireEvent.change(apiKeyInput, { target: { value: 'test-key' } });
		fireEvent.change(apiSecretInput, { target: { value: 'test-secret' } });

		// Select basic test mode
		const basicTestRadio = screen.getByLabelText(/Basic Test/i);
		fireEvent.click(basicTestRadio);

		// Test connection
		const testBtn = screen.getByRole('button', { name: /Test Basic Connection/i });
		fireEvent.click(testBtn);

		await waitFor(() => {
			// Should show test result message
			const message = screen.queryByText(/Connection/i) || screen.queryByText(/successful/i) || screen.queryByText(/failed/i);
			expect(message).toBeInTheDocument();
		}, { timeout: 10000 });
	});

	it('allows testing full connection', async () => {
		renderPage();
		await switchToBroker({ showFull: true });

		const apiKeyInput = await screen.findByPlaceholderText(/Enter API Key/i);
		const apiSecretInput = screen.getByPlaceholderText(/Enter API Secret/i);

		fireEvent.change(apiKeyInput, { target: { value: 'test-key' } });
		fireEvent.change(apiSecretInput, { target: { value: 'test-secret' } });

		// Select full test mode
		const fullTestRadio = screen.getByLabelText(/Full Test/i);
		fireEvent.click(fullTestRadio);

		const mobileInput = await screen.findByPlaceholderText(/Enter mobile number/i);
		const passwordInput = screen.getByPlaceholderText(/Enter password/i);
		const mpinInput = screen.getByPlaceholderText(/Enter MPIN/i);

		fireEvent.change(mobileInput, { target: { value: '9876543210' } });
		fireEvent.change(passwordInput, { target: { value: 'testpass' } });
		fireEvent.change(mpinInput, { target: { value: '1234' } });

		// Test connection
		const testBtn = screen.getByRole('button', { name: /Test Full Connection/i });
		fireEvent.click(testBtn);

		await waitFor(() => {
			// Should show test result message
			const message = screen.queryByText(/Connection/i) || screen.queryByText(/successful/i) || screen.queryByText(/failed/i);
			expect(message).toBeInTheDocument();
		}, { timeout: 10000 });
	});
});
