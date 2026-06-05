import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { BillingPage } from '../dashboard/BillingPage';
import * as billingApi from '@/api/billing';
import { useSessionStore } from '@/state/sessionStore';

vi.mock('@/api/billing', () => ({
	getMyBillingTransactions: vi.fn(),
	getPerformanceBills: vi.fn(),
	getBillingPaymentOptions: vi.fn(),
	checkoutPerformanceBill: vi.fn(),
	createRazorpayOrder: vi.fn(),
	verifyRazorpayPayment: vi.fn(),
}));

const onlinePaymentOptions = {
	online_payments_enabled: true,
	offline_upi_id: null,
	offline_instructions: null,
	offline_qr_image_url: null,
};

function mockOnlineCheckoutEnabled() {
	vi.mocked(billingApi.getBillingPaymentOptions).mockResolvedValue(onlinePaymentOptions as never);
}

const offlinePaymentOptions = {
	online_payments_enabled: false,
	offline_upi_id: 'beta@paytm',
	offline_instructions: 'Include bill # in note',
	offline_qr_image_url: null,
};

function mockOfflinePaymentEnabled() {
	vi.mocked(billingApi.getBillingPaymentOptions).mockResolvedValue(offlinePaymentOptions as never);
}

describe('BillingPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		useSessionStore.setState({ isAdmin: false, user: { id: 1, email: 'u@x.com', roles: ['user'] } as never });
		vi.mocked(billingApi.getMyBillingTransactions).mockResolvedValue([
			{ id: 1, status: 'paid', amount_paise: 50000, created_at: '2025-01-01' },
		] as never);
		vi.mocked(billingApi.getPerformanceBills).mockResolvedValue([]);
		mockOfflinePaymentEnabled();
	});

	it('renders billing sections with transaction history', async () => {
		render(withProviders(<BillingPage />));

		await waitFor(() => {
			expect(screen.getByText('Billing')).toBeInTheDocument();
			expect(screen.getByText('No performance fee bills yet.')).toBeInTheDocument();
			expect(screen.getByText('paid')).toBeInTheDocument();
			expect(screen.getByText('₹500.00')).toBeInTheDocument();
		});
	});

	it('shows offline UPI instructions instead of Pay now when online checkout disabled', async () => {
		mockOfflinePaymentEnabled();
		vi.mocked(billingApi.getPerformanceBills).mockResolvedValue([
			{
				id: 10,
				bill_month: '2025-01',
				status: 'pending_payment',
				due_at: '2025-02-01T00:00:00',
				paid_at: null,
				current_month_pnl: 1000,
				fee_percentage: 10,
				payable_amount: 100,
			},
		] as never);

		render(withProviders(<BillingPage />));

		await waitFor(() => {
			expect(screen.getAllByText('beta@paytm').length).toBeGreaterThan(0);
			expect(screen.getAllByText(/Pay via UPI/i).length).toBeGreaterThan(0);
		});
		expect(screen.queryByRole('button', { name: /Pay now/i })).not.toBeInTheDocument();
	});

	it('shows performance bills with pay button for pending bills when online enabled', async () => {
		mockOnlineCheckoutEnabled();
		vi.mocked(billingApi.getPerformanceBills).mockResolvedValue([
			{
				id: 10,
				bill_month: '2025-01',
				status: 'pending_payment',
				due_at: '2025-02-01T00:00:00',
				paid_at: null,
				current_month_pnl: 1000,
				fee_percentage: 10,
				payable_amount: 100,
			},
		] as never);

		render(withProviders(<BillingPage />));

		await waitFor(() => {
			expect(screen.getAllByText(/2025-01/).length).toBeGreaterThan(0);
			expect(screen.getByRole('button', { name: 'Pay now (online)' })).toBeInTheDocument();
		});
	});

	it('starts performance fee checkout and verifies payment', async () => {
		mockOnlineCheckoutEnabled();
		vi.mocked(billingApi.getPerformanceBills).mockResolvedValue([
			{
				id: 10,
				bill_month: '2025-01',
				status: 'pending_payment',
				due_at: '2025-02-01T00:00:00',
				paid_at: null,
				current_month_pnl: 1000,
				fee_percentage: 10,
				payable_amount: 100,
			},
		] as never);
		vi.mocked(billingApi.checkoutPerformanceBill).mockResolvedValue({
			bill_id: 10,
			razorpay_key_id: 'key',
			order_id: 'order_1',
			amount_paise: 10000,
			currency: 'INR',
		} as never);

		const openMock = vi.fn();
		let capturedHandler: ((response: Record<string, string>) => void) | undefined;
		function RazorpayMock(this: { open: typeof openMock; on?: (event: string, cb: (r: unknown) => void) => void }, opts: {
			handler: (r: Record<string, string>) => void;
			modal?: { ondismiss?: () => void };
		}) {
			capturedHandler = opts.handler;
			this.open = openMock;
			this.on = vi.fn();
		}
		window.Razorpay = RazorpayMock as never;

		render(withProviders(<BillingPage />));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Pay now (online)' })).toBeInTheDocument());

		fireEvent.click(screen.getByRole('button', { name: 'Pay now (online)' }));
		await waitFor(() => {
			expect(billingApi.checkoutPerformanceBill).toHaveBeenCalledWith(10);
			expect(openMock).toHaveBeenCalled();
		});

		vi.mocked(billingApi.verifyRazorpayPayment).mockResolvedValue({ verified: true } as never);
		capturedHandler?.({
			razorpay_payment_id: 'pay_2',
			razorpay_order_id: 'order_1',
			razorpay_signature: 'sig2',
		});
		await waitFor(() => {
			expect(screen.getByText(/Payment verified/i)).toBeInTheDocument();
		});
	});

	it('shows checkout error when performance payment fails to start', async () => {
		mockOnlineCheckoutEnabled();
		vi.mocked(billingApi.getPerformanceBills).mockResolvedValue([
			{
				id: 11,
				bill_month: '2025-02',
				status: 'overdue',
				due_at: '2025-03-01T00:00:00',
				paid_at: null,
				current_month_pnl: 500,
				fee_percentage: 10,
				payable_amount: 50,
			},
		] as never);
		vi.mocked(billingApi.checkoutPerformanceBill).mockRejectedValue({
			response: { data: { detail: 'Checkout unavailable' } },
		});

		render(withProviders(<BillingPage />));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Pay now (online)' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Pay now (online)' }));

		await waitFor(() => {
			expect(screen.getByText(/Checkout unavailable/i)).toBeInTheDocument();
		});
	});

	it('opens test checkout panel via admin button when no bills', async () => {
		mockOnlineCheckoutEnabled();
		useSessionStore.setState({ isAdmin: true, user: { id: 1, email: 'a@x.com', roles: ['admin'] } as never });
		render(withProviders(<BillingPage />));

		await waitFor(() => expect(screen.getByText('No performance fee bills yet.')).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Test Razorpay checkout' }));
		expect(screen.getByText(/Dev — Test Razorpay checkout/i)).toBeInTheDocument();
	});

	it('runs admin test checkout and reports unverified payment', async () => {
		mockOnlineCheckoutEnabled();
		useSessionStore.setState({ isAdmin: true, user: { id: 1, email: 'a@x.com', roles: ['admin'] } as never });
		const openMock = vi.fn();
		let capturedHandler: ((response: Record<string, string>) => void) | undefined;
		function RazorpayMock(this: { open: typeof openMock; on?: (event: string, cb: (r: unknown) => void) => void }, opts: {
			handler: (r: Record<string, string>) => void;
		}) {
			capturedHandler = opts.handler;
			this.open = openMock;
			this.on = vi.fn();
		}
		window.Razorpay = RazorpayMock as never;

		render(withProviders(<BillingPage />));
		await waitFor(() => expect(screen.getByText(/Dev — Test Razorpay checkout/i)).toBeInTheDocument());

		vi.mocked(billingApi.createRazorpayOrder).mockResolvedValue({
			key_id: 'k',
			order_id: 'o',
			amount: 200,
			currency: 'INR',
		} as never);
		fireEvent.click(screen.getByRole('button', { name: 'Pay (test)' }));
		await waitFor(() => expect(openMock).toHaveBeenCalled());

		vi.mocked(billingApi.verifyRazorpayPayment).mockResolvedValue({ verified: false, detail: 'Bad signature' } as never);
		capturedHandler?.({
			razorpay_payment_id: 'pay_x',
			razorpay_order_id: 'o',
			razorpay_signature: 'bad',
		});
		await waitFor(() => {
			expect(screen.getByText(/Bad signature/i)).toBeInTheDocument();
		});
	});

	it('shows checkout dismissed message for performance fee payment', async () => {
		mockOnlineCheckoutEnabled();
		vi.mocked(billingApi.getPerformanceBills).mockResolvedValue([
			{
				id: 10,
				bill_month: '2025-01',
				status: 'pending_payment',
				due_at: '2025-02-01T00:00:00',
				paid_at: null,
				current_month_pnl: 1000,
				fee_percentage: 10,
				payable_amount: 100,
			},
		] as never);
		vi.mocked(billingApi.checkoutPerformanceBill).mockResolvedValue({
			bill_id: 10,
			razorpay_key_id: 'key',
			order_id: 'order_1',
			amount_paise: 10000,
			currency: 'INR',
		} as never);

		let onDismiss: (() => void) | undefined;
		function RazorpayMock(this: { open: () => void }, opts: { modal?: { ondismiss?: () => void } }) {
			onDismiss = opts.modal?.ondismiss;
			this.open = vi.fn();
		}
		window.Razorpay = RazorpayMock as never;

		render(withProviders(<BillingPage />));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Pay now (online)' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Pay now (online)' }));
		await waitFor(() => expect(onDismiss).toBeDefined());

		onDismiss?.();
		await waitFor(() => {
			expect(screen.getByText(/Checkout closed before completion/i)).toBeInTheDocument();
		});
	});

	it('shows verification error when performance payment verify fails', async () => {
		mockOnlineCheckoutEnabled();
		vi.mocked(billingApi.getPerformanceBills).mockResolvedValue([
			{
				id: 10,
				bill_month: '2025-01',
				status: 'overdue',
				due_at: '2025-02-01T00:00:00',
				paid_at: null,
				current_month_pnl: 1000,
				fee_percentage: 10,
				payable_amount: 100,
			},
		] as never);
		vi.mocked(billingApi.checkoutPerformanceBill).mockResolvedValue({
			bill_id: 10,
			razorpay_key_id: 'key',
			order_id: 'order_1',
			amount_paise: 10000,
			currency: 'INR',
		} as never);

		let capturedHandler: ((response: Record<string, string>) => void) | undefined;
		function RazorpayMock(this: { open: () => void }, opts: { handler: (r: Record<string, string>) => void }) {
			capturedHandler = opts.handler;
			this.open = vi.fn();
		}
		window.Razorpay = RazorpayMock as never;

		render(withProviders(<BillingPage />));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Pay now (online)' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Pay now (online)' }));
		await waitFor(() => expect(capturedHandler).toBeDefined());

		vi.mocked(billingApi.verifyRazorpayPayment).mockRejectedValue({
			response: { data: { detail: { code: 'SIG_FAIL' } } },
		});
		capturedHandler?.({
			razorpay_payment_id: 'pay_3',
			razorpay_order_id: 'order_1',
			razorpay_signature: 'sig3',
		});
		await waitFor(() => {
			expect(screen.getByText(/SIG_FAIL/)).toBeInTheDocument();
		});
	});

	it('displays paid bill details and handles test payment failure event', async () => {
		mockOnlineCheckoutEnabled();
		useSessionStore.setState({ isAdmin: true, user: { id: 1, email: 'a@x.com', roles: ['admin'] } as never });
		vi.mocked(billingApi.getPerformanceBills).mockResolvedValue([
			{
				id: 5,
				bill_month: '2024-12',
				status: 'paid',
				due_at: '2025-01-01T00:00:00',
				paid_at: '2025-01-05T12:00:00',
				current_month_pnl: 2000,
				fee_percentage: 10,
				payable_amount: 0,
			},
		] as never);

		let paymentFailedCb: ((r: unknown) => void) | undefined;
		function RazorpayMock(this: { open: () => void; on: (ev: string, cb: (r: unknown) => void) => void }, opts: {
			handler: (r: Record<string, string>) => void;
		}) {
			this.open = vi.fn();
			this.on = vi.fn((ev, cb) => {
				if (ev === 'payment.failed') paymentFailedCb = cb;
			});
		}
		window.Razorpay = RazorpayMock as never;

		render(withProviders(<BillingPage />));
		await waitFor(() => expect(screen.getByText(/Paid 2025-01-05/i)).toBeInTheDocument());

		vi.mocked(billingApi.createRazorpayOrder).mockResolvedValue({
			key_id: 'k',
			order_id: 'o',
			amount: 200,
			currency: 'INR',
		} as never);
		fireEvent.click(screen.getByRole('button', { name: 'Pay (test)' }));
		await waitFor(() => expect(paymentFailedCb).toBeDefined());
		paymentFailedCb?.({ reason: 'timeout' });
		await waitFor(() => {
			expect(screen.getByText(/Payment failed/i)).toBeInTheDocument();
		});
	});

	it('reports when checkout data is incomplete for performance payment', async () => {
		mockOnlineCheckoutEnabled();
		vi.mocked(billingApi.getPerformanceBills).mockResolvedValue([
			{
				id: 10,
				bill_month: '2025-01',
				status: 'pending_payment',
				due_at: '2025-02-01T00:00:00',
				paid_at: null,
				current_month_pnl: 1000,
				fee_percentage: 10,
				payable_amount: 100,
			},
		] as never);
		vi.mocked(billingApi.checkoutPerformanceBill).mockResolvedValue({
			bill_id: 10,
			razorpay_key_id: '',
			order_id: '',
			amount_paise: 10000,
			currency: 'INR',
		} as never);

		render(withProviders(<BillingPage />));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Pay now (online)' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Pay now (online)' }));
		await waitFor(() => {
			expect(screen.getByText(/Razorpay is not available or checkout data is incomplete/i)).toBeInTheDocument();
		});
	});

	it('updates test checkout amount input', async () => {
		mockOnlineCheckoutEnabled();
		useSessionStore.setState({ isAdmin: true, user: { id: 1, email: 'a@x.com', roles: ['admin'] } as never });
		render(withProviders(<BillingPage />));
		await waitFor(() => expect(screen.getByText(/Dev — Test Razorpay checkout/i)).toBeInTheDocument());

		const amountInput = screen.getByLabelText(/Amount \(paise\)/i);
		fireEvent.change(amountInput, { target: { value: '250' } });
		expect((amountInput as HTMLInputElement).value).toBe('250');
	});

	it('shows error when test checkout order creation fails', async () => {
		mockOnlineCheckoutEnabled();
		useSessionStore.setState({ isAdmin: true, user: { id: 1, email: 'a@x.com', roles: ['admin'] } as never });
		vi.mocked(billingApi.createRazorpayOrder).mockRejectedValue({
			response: { data: { detail: 'Order create failed' } },
		});

		render(withProviders(<BillingPage />));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Pay (test)' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Pay (test)' }));

		await waitFor(() => {
			expect(screen.getByText(/Order create failed/i)).toBeInTheDocument();
		});
	});
});
