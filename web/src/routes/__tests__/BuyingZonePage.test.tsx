import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { BuyingZonePage } from '../dashboard/BuyingZonePage';
import { withProviders } from '@/test/utils';

describe('BuyingZonePage', () => {
	it('renders signals rows from API', async () => {
		render(withProviders(<MemoryRouter initialEntries={['/dashboard/buying-zone']}><BuyingZonePage /></MemoryRouter>));
		expect(await screen.findByText(/Buying Zone/i)).toBeInTheDocument();
		expect(await screen.findByText('TCS')).toBeInTheDocument();
	});
});
