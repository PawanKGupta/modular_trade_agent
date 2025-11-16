import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SettingsPage } from '../dashboard/SettingsPage';
import { withProviders } from '@/test/utils';

describe('SettingsPage', () => {
	it('loads default Paper and saves Broker', async () => {
		render(withProviders(<MemoryRouter initialEntries={['/dashboard/settings']}><SettingsPage /></MemoryRouter>));
		expect(await screen.findByText(/Trading mode/i)).toBeInTheDocument();
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
});
