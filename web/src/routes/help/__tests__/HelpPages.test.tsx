import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HelpHomePage } from '../HelpHomePage';
import { HelpLayout } from '../HelpLayout';
import { HelpGetStartedPage } from '../HelpGetStartedPage';
import { withProviders } from '@/test/utils';

function renderHelp(path: string) {
	return render(
		withProviders(
			<MemoryRouter initialEntries={[path]}>
				<Routes>
					<Route path="/help" element={<HelpLayout />}>
						<Route index element={<HelpHomePage />} />
						<Route path="get-started" element={<HelpGetStartedPage />} />
					</Route>
				</Routes>
			</MemoryRouter>,
		),
	);
}

describe('Help center', () => {
	it('renders welcome page with navigation to get started', () => {
		renderHelp('/help');
		expect(screen.getByRole('heading', { name: /welcome to rebound/i })).toBeInTheDocument();
		const getStartedLinks = screen.getAllByRole('link', { name: /get started/i });
		expect(getStartedLinks.some((el) => el.getAttribute('href') === '/help/get-started')).toBe(true);
		expect(screen.getByRole('link', { name: /log in/i })).toHaveAttribute('href', '/login');
	});

	it('renders get started with signup link', () => {
		renderHelp('/help/get-started');
		expect(screen.getByRole('heading', { name: /^get started$/i })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: /^sign up$/i })).toHaveAttribute('href', '/signup');
	});
});
