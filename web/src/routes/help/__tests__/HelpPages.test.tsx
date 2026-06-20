import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HelpHomePage } from '../HelpHomePage';
import { HelpLayout } from '../HelpLayout';
import { HelpGetStartedPage } from '../HelpGetStartedPage';
import { HelpKotakApiPage } from '../HelpKotakApiPage';
import { HelpConnectKotakPage } from '../HelpConnectKotakPage';
import { HelpBillingPage } from '../HelpBillingPage';
import { HelpFaqPage } from '../HelpFaqPage';
import { HelpMLPage } from '../HelpMLPage';
import { HELP_LEGACY_SLUG, HELP_NAV_ITEMS, HELP_SLUG } from '../helpNav';
import { withProviders } from '@/test/utils';

const HELP_ROUTES: { path: string; name: RegExp }[] = [
	{ path: '/help', name: /welcome to rebound/i },
	{ path: '/help/get-started', name: /^get started$/i },
	{ path: '/help/broker-api', name: /broker api setup/i },
	{ path: '/help/connect-broker', name: /connect your broker/i },
	{ path: '/help/billing', name: /performance fees/i },
	{ path: '/help/faq', name: /^faq$/i },
	{ path: '/help/ml-signals', name: /ML-powered signals/i },
];

function renderHelpAt(path: string) {
	return render(
		withProviders(
			<MemoryRouter initialEntries={[path]}>
				<Routes>
					<Route path="/help" element={<HelpLayout />}>
						<Route index element={<HelpHomePage />} />
						<Route path="get-started" element={<HelpGetStartedPage />} />
						<Route path="broker-api" element={<HelpKotakApiPage />} />
						<Route path="connect-broker" element={<HelpConnectKotakPage />} />
						<Route path="billing" element={<HelpBillingPage />} />
						<Route path="faq" element={<HelpFaqPage />} />
						<Route path="ml-signals" element={<HelpMLPage />} />
					</Route>
				</Routes>
			</MemoryRouter>,
		),
	);
}

/** Help is end-user only: no repo docs, GitHub, or other external developer URLs. */
function assertNoDevDocLinks(container: HTMLElement) {
	const links = within(container).queryAllByRole('link');
	for (const link of links) {
		const href = link.getAttribute('href') ?? '';
		expect(href).not.toMatch(/^https?:\/\//i);
		expect(href).not.toMatch(/github\.com/i);
		expect(href).not.toMatch(/\.md($|[?#])/i);
		expect(href).not.toMatch(/^docs\//i);
		if (href.startsWith('/')) {
			expect(
				href.startsWith('/help') ||
					href.startsWith('/login') ||
					href.startsWith('/signup') ||
					href.startsWith('/dashboard') ||
					href.startsWith('/resend-verification'),
			).toBe(true);
		}
	}
}

describe('Help center', () => {
	it('renders welcome page with navigation to get started', () => {
		renderHelpAt('/help');
		expect(screen.getByRole('heading', { name: /welcome to rebound/i })).toBeInTheDocument();
		expect(screen.queryByText(/kotak neo/i)).not.toBeInTheDocument();
		const getStartedLinks = screen.getAllByRole('link', { name: /get started/i });
		expect(getStartedLinks.some((el) => el.getAttribute('href') === '/help/get-started')).toBe(true);
		expect(screen.getByRole('link', { name: /log in/i })).toHaveAttribute('href', '/login');
	});

	it('renders get started with signup link', () => {
		renderHelpAt('/help/get-started');
		expect(screen.getByRole('heading', { name: /^get started$/i })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: /^sign up$/i })).toHaveAttribute('href', '/signup');
	});

	it.each(HELP_ROUTES)('does not link to repo or GitHub docs on $path', ({ path }) => {
		const { container } = renderHelpAt(path);
		assertNoDevDocLinks(container);
	});

	it('renders FAQ with in-app billing links', () => {
		renderHelpAt('/help/faq');
		expect(screen.getByRole('heading', { name: /how do performance fees work/i })).toBeInTheDocument();
		const main = screen.getByRole('main');
		expect(within(main).getByRole('link', { name: /performance fees/i })).toHaveAttribute('href', '/help/billing');
		expect(within(main).getByRole('link', { name: /^billing$/i })).toHaveAttribute('href', '/dashboard/billing');
	});

	it('nav items use broker-neutral slugs', () => {
		expect(HELP_NAV_ITEMS.length).toBeGreaterThan(0);
		for (const item of HELP_NAV_ITEMS) {
			const path = item.slug ? `/help/${item.slug}` : '/help';
			expect(path).toMatch(/^\/help(\/[a-z-]+)?$/);
		}
		expect(HELP_SLUG.brokerApi).toBe('broker-api');
		expect(HELP_SLUG.connectBroker).toBe('connect-broker');
		expect(HELP_LEGACY_SLUG.kotakApi).toBe('kotak-api');
	});

	it('renders ML-powered signals help page', () => {
		renderHelpAt('/help/ml-signals');
		expect(screen.getByRole('heading', { name: /ML-powered signals/i })).toBeInTheDocument();
		expect(screen.getByText(/What the ML engine does/i)).toBeInTheDocument();
		expect(screen.getByText(/Walk-forward validated/i)).toBeInTheDocument();
	});
});
