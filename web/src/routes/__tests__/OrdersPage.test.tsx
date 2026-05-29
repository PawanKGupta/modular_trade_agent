import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { OrdersPage } from '../dashboard/OrdersPage';

describe('OrdersPage', () => {
	it('switches tabs and displays orders for each status', async () => {
		render(withProviders(<OrdersPage />));

		// Default Pending (merged: AMO + PENDING_EXECUTION)
		await screen.findByText(/Pending Orders/i);
		await screen.findByText('INFY');
		await screen.findByText('1500.00');

		// Ongoing
		fireEvent.click(screen.getByRole('button', { name: 'Ongoing' }));
		await screen.findByText(/Ongoing Orders/i);
		await screen.findByText('RELIANCE');

		// Failed (merged: FAILED + RETRY_PENDING + REJECTED)
		fireEvent.click(screen.getByRole('button', { name: 'Failed' }));
		await screen.findByText(/Failed Orders/i);
		await screen.findByText('TCS');

		// Closed
		fireEvent.click(screen.getByRole('button', { name: 'Closed' }));
		await screen.findByText(/Closed Orders/i);
		await screen.findByText('HDFCBANK');

		// Cancelled
		fireEvent.click(screen.getByRole('button', { name: 'Cancelled' }));
		await screen.findByText(/Cancelled Orders/i);
		await screen.findByText('WIPRO');
	});
});

describe('OrdersPage interactions', () => {
	it('filters by trade mode and opens export panel', async () => {
		render(withProviders(<OrdersPage />));

		await screen.findByText('INFY');
		fireEvent.click(screen.getByRole('button', { name: 'Paper' }));
		fireEvent.click(screen.getByRole('button', { name: /Export/i }));
		expect(screen.getByText('Export Orders')).toBeInTheDocument();
	});

	it('syncs orders from refresh button', async () => {
		render(withProviders(<OrdersPage />));
		await screen.findByText('INFY');
		fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));
		await screen.findByText('INFY');
	});

	it('retries and drops failed orders', async () => {
		const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
		render(withProviders(<OrdersPage />));

		fireEvent.click(screen.getByRole('button', { name: 'Failed' }));
		await screen.findByText('TCS');

		fireEvent.click(screen.getByRole('button', { name: /Retry/i }));
		fireEvent.click(screen.getByRole('button', { name: /Drop/i }));

		await screen.findByText('TCS');
		confirmSpy.mockRestore();
	});

	it('filters broker orders and paginates pending list', async () => {
		const { server } = await import('@/mocks/server');
		const { http, HttpResponse } = await import('msw');
		const API = (path: string) => `http://localhost:8000/api/v1${path}`;
		const manyPending = Array.from({ length: 30 }, (_, i) => ({
			id: 1000 + i,
			symbol: `SYM${i}`,
			side: 'buy',
			quantity: 1,
			price: 100 + i,
			status: 'pending',
			reason: 'Waiting',
			trade_mode_display: i % 2 === 0 ? 'Paper' : 'Kotak Neo',
			created_at: new Date().toISOString(),
			updated_at: new Date().toISOString(),
		}));

		server.use(
			http.get(API('/user/orders'), ({ request }) => {
				const reqUrl = new URL(request.url);
				const page = Number(reqUrl.searchParams.get('page') ?? '1');
				const pageSize = Number(reqUrl.searchParams.get('page_size') ?? '50');
				const start = (page - 1) * pageSize;
				const items = manyPending.slice(start, start + pageSize);
				return HttpResponse.json({
					items,
					total: manyPending.length,
					page,
					page_size: pageSize,
					total_pages: Math.ceil(manyPending.length / pageSize),
				});
			})
		);

		render(withProviders(<OrdersPage />));
		await screen.findByText('SYM0');

		fireEvent.click(screen.getByRole('button', { name: 'Broker' }));
		await screen.findByText('SYM1');

		const pageSizeSelect = screen.getAllByRole('combobox').find(
			(el) => (el as HTMLSelectElement).value === '50'
		);
		expect(pageSizeSelect).toBeTruthy();
		fireEvent.change(pageSizeSelect!, { target: { value: '25' } });
		await screen.findByText(/Showing 1 to 25 of 30/i);

		fireEvent.click(screen.getByRole('button', { name: '2' }));
		await screen.findByText('SYM25');
	});

	it('shows ongoing execution details and empty tab state', async () => {
		render(withProviders(<OrdersPage />));

		fireEvent.click(screen.getByRole('button', { name: 'Ongoing' }));
		await screen.findByText('RELIANCE');
		expect(screen.getAllByText('2400.00').length).toBeGreaterThan(0);

		const { server } = await import('@/mocks/server');
		const { http, HttpResponse } = await import('msw');
		server.use(
			http.get('http://localhost:8000/api/v1/user/orders', ({ request }) => {
				const reqUrl = new URL(request.url);
				if (reqUrl.searchParams.get('status') === 'cancelled') {
					return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50, total_pages: 1 });
				}
				return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50, total_pages: 1 });
			})
		);

		fireEvent.click(screen.getByRole('button', { name: 'Cancelled' }));
		await screen.findByText(/No orders/i);
	});

	it('uses first/last pagination controls with many pages', async () => {
		const { server } = await import('@/mocks/server');
		const { http, HttpResponse } = await import('msw');
		const API = (path: string) => `http://localhost:8000/api/v1${path}`;
		const manyPending = Array.from({ length: 150 }, (_, i) => ({
			id: 2000 + i,
			symbol: `BIG${i}`,
			side: 'buy',
			quantity: 1,
			price: 100,
			status: 'pending',
			reason: 'Waiting',
			trade_mode_display: 'Paper',
			created_at: new Date().toISOString(),
			updated_at: new Date().toISOString(),
		}));

		server.use(
			http.get(API('/user/orders'), ({ request }) => {
				const reqUrl = new URL(request.url);
				const page = Number(reqUrl.searchParams.get('page') ?? '1');
				const pageSize = Number(reqUrl.searchParams.get('page_size') ?? '50');
				const start = (page - 1) * pageSize;
				return HttpResponse.json({
					items: manyPending.slice(start, start + pageSize),
					total: manyPending.length,
					page,
					page_size: pageSize,
					total_pages: Math.ceil(manyPending.length / pageSize),
				});
			})
		);

		render(withProviders(<OrdersPage />));
		await screen.findByText('BIG0');

		const pageSizeSelect = screen.getAllByRole('combobox').find(
			(el) => (el as HTMLSelectElement).value === '50'
		)!;
		fireEvent.change(pageSizeSelect, { target: { value: '25' } });
		await screen.findByText(/Showing 1 to 25 of 150/i);

		fireEvent.click(screen.getByRole('button', { name: '««' }));
		expect(screen.getByText('BIG0')).toBeInTheDocument();

		fireEvent.click(screen.getByRole('button', { name: '»»' }));
		await screen.findByText('BIG125');

		fireEvent.click(screen.getByRole('button', { name: '4' }));
		await screen.findByText('BIG75');
	});

	it('cancels drop when confirmation rejected', async () => {
		const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
		render(withProviders(<OrdersPage />));

		fireEvent.click(screen.getByRole('button', { name: 'Failed' }));
		await screen.findByText('TCS');
		fireEvent.click(screen.getByRole('button', { name: /Drop/i }));
		expect(confirmSpy).toHaveBeenCalled();
		confirmSpy.mockRestore();
	});
});
