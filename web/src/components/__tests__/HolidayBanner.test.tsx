import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HolidayBanner } from '../HolidayBanner';
import * as serviceApi from '@/api/service';

vi.mock('@/api/service', () => ({
	getTradingDayInfo: vi.fn(),
}));

const wrapper = ({ children }: { children: React.ReactNode }) => (
	<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
		{children}
	</QueryClientProvider>
);

describe('HolidayBanner', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders nothing when market is open', async () => {
		vi.mocked(serviceApi.getTradingDayInfo).mockResolvedValue({
			is_holiday: false,
			holiday_name: null,
		} as never);
		const { container } = render(<HolidayBanner />, { wrapper });
		await waitFor(() => expect(serviceApi.getTradingDayInfo).toHaveBeenCalled());
		expect(container).toBeEmptyDOMElement();
	});

	it('shows holiday marquee and toggles pause on tap', async () => {
		vi.mocked(serviceApi.getTradingDayInfo).mockResolvedValue({
			is_holiday: true,
			holiday_name: 'Diwali',
		} as never);
		render(<HolidayBanner />, { wrapper });

		await waitFor(() => {
			expect(screen.getAllByText(/NSE Holiday: Diwali/i).length).toBeGreaterThan(0);
		});

		const marquee = screen.getByRole('button', { name: /pause\/resume holiday message/i });
		fireEvent.click(marquee);
		expect(document.querySelector('.marquee-content.paused')).toBeTruthy();
	});
});
