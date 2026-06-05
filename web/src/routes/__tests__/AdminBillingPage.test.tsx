import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { AdminBillingPage } from '../dashboard/AdminBillingPage';
import * as billingApi from '@/api/billing';

vi.mock('@/api/billing', () => ({
	getAdminBillingSettings: vi.fn(),
	getAdminTransactions: vi.fn(),
	getAdminOpenPerformanceBills: vi.fn(),
	patchAdminBillingSettings: vi.fn(),
	patchAdminRazorpayCredentials: vi.fn(),
	postAdminRefund: vi.fn(),
	recordAdminCashPayment: vi.fn(),
	runBillingReconcile: vi.fn(),
	uploadAdminOfflinePaymentQr: vi.fn(),
	deleteAdminOfflinePaymentQr: vi.fn(),
	fetchOfflinePaymentQrBlob: vi.fn(),
}));

describe('AdminBillingPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(billingApi.getAdminBillingSettings).mockResolvedValue({
			payment_card_enabled: true,
			payment_upi_enabled: false,
			online_payments_enabled: false,
			offline_payment_upi_id: 'beta@paytm',
			offline_payment_instructions: 'Pay exact amount',
			offline_payment_qr_image_url: 'https://example.com/qr.png',
			offline_payment_qr_uploaded: false,
			razorpay_key_id_preview: 'rzp_test',
			razorpay_api_configured: true,
			razorpay_webhook_configured: false,
		} as never);
		vi.mocked(billingApi.getAdminTransactions).mockResolvedValue([
			{ id: 1, user_id: 2, status: 'paid', amount_paise: 10000, created_at: '2025-01-01' },
		] as never);
		vi.mocked(billingApi.patchAdminBillingSettings).mockResolvedValue({} as never);
		vi.mocked(billingApi.patchAdminRazorpayCredentials).mockResolvedValue({} as never);
		vi.mocked(billingApi.runBillingReconcile).mockResolvedValue({ updated: 1 } as never);
		vi.mocked(billingApi.postAdminRefund).mockResolvedValue({} as never);
		vi.mocked(billingApi.getAdminOpenPerformanceBills).mockResolvedValue([]);
		vi.mocked(billingApi.recordAdminCashPayment).mockResolvedValue({
			bill_id: 1,
			user_id: 2,
			billing_transaction_id: 9,
			amount_paise: 2281,
			paid_at: '2026-06-04T00:00:00',
		} as never);
	});

	it('renders admin billing settings and transactions', async () => {
		render(withProviders(<AdminBillingPage />));

		await waitFor(() => {
			expect(screen.getByText('Admin — Billing')).toBeInTheDocument();
			expect(screen.getByText('rzp_test')).toBeInTheDocument();
		});
		expect(screen.getAllByText('paid').length).toBeGreaterThan(0);
	});

	it('toggles payment methods', async () => {
		render(withProviders(<AdminBillingPage />));

		const upi = await screen.findByRole('checkbox', { name: /UPI in Razorpay modal/i });
		expect(upi).toBeTruthy();
		fireEvent.click(upi!);

		await waitFor(() => {
			expect(billingApi.patchAdminBillingSettings.mock.calls[0][0]).toEqual({
				payment_upi_enabled: true,
			});
		});
	});

	it('saves razorpay credentials and runs reconcile', async () => {
		render(withProviders(<AdminBillingPage />));

		await waitFor(() => expect(screen.getByPlaceholderText('rzp_…')).toBeInTheDocument());

		fireEvent.change(screen.getByPlaceholderText('rzp_…'), { target: { value: 'rzp_new' } });
		fireEvent.click(screen.getByRole('button', { name: 'Save Razorpay credentials' }));

		await waitFor(() => {
			expect(billingApi.patchAdminRazorpayCredentials).toHaveBeenCalled();
		});

		fireEvent.click(screen.getByRole('button', { name: 'Run reconcile' }));
		await waitFor(() => {
			expect(billingApi.runBillingReconcile).toHaveBeenCalled();
		});
	});

	it('submits refund when transaction id provided', async () => {
		render(withProviders(<AdminBillingPage />));

		await waitFor(() => expect(screen.getByText('Refund')).toBeInTheDocument());

		const refundSection = screen.getByText('Refund').closest('section') as HTMLElement;
		const txInput = within(refundSection).getAllByRole('textbox')[0];
		fireEvent.change(txInput, { target: { value: '99' } });
		fireEvent.click(screen.getByRole('button', { name: 'Submit refund' }));

		await waitFor(() => {
			expect(billingApi.postAdminRefund.mock.calls[0][0]).toEqual(
				expect.objectContaining({ billing_transaction_id: 99 })
			);
		});
	});

	it('shows message when saving credentials without changes', async () => {
		render(withProviders(<AdminBillingPage />));

		await waitFor(() => expect(screen.getByRole('button', { name: 'Save Razorpay credentials' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Save Razorpay credentials' }));

		await waitFor(() => {
			expect(screen.getByText(/Change a Razorpay field/i)).toBeInTheDocument();
		});
	});

	it('loads open performance bills and records cash payment', async () => {
		vi.mocked(billingApi.getAdminOpenPerformanceBills).mockResolvedValue([
			{
				id: 5,
				user_id: 2,
				user_email: 'user2@test.com',
				bill_month: '2026-05-01',
				generated_at: '2026-05-31T12:00:00',
				due_at: '2026-06-15T12:00:00',
				status: 'overdue',
				payable_amount: 22.81,
				fee_amount: 22.81,
				chargeable_profit: 228.05,
				current_month_pnl: 228.05,
				previous_carry_forward_loss: 0,
				new_carry_forward_loss: 0,
				fee_percentage: 10,
				paid_at: null,
				razorpay_order_id: null,
			},
		] as never);
		vi.mocked(billingApi.recordAdminCashPayment).mockResolvedValue({
			bill_id: 5,
			user_id: 2,
			billing_transaction_id: 9,
			amount_paise: 2281,
			paid_at: '2026-06-04T00:00:00',
		} as never);
		const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

		render(withProviders(<AdminBillingPage />));
		await waitFor(() =>
			expect(screen.getByRole('heading', { name: 'Record cash payment' })).toBeInTheDocument()
		);

		fireEvent.change(screen.getByPlaceholderText('e.g. 2'), { target: { value: '2' } });
		fireEvent.change(screen.getByPlaceholderText('Receipt ref, date, etc.'), {
			target: { value: 'Desk cash' },
		});
		fireEvent.click(screen.getByRole('button', { name: 'Load open bills' }));

		await waitFor(() => {
			expect(billingApi.getAdminOpenPerformanceBills).toHaveBeenCalledWith({
				user_id: 2,
				limit: 100,
			});
			expect(screen.getByText('user2@test.com')).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: 'Mark paid' }));

		await waitFor(() => {
			expect(billingApi.recordAdminCashPayment).toHaveBeenCalledWith(5, { note: 'Desk cash' });
			expect(screen.getByText(/Cash payment recorded for bill #5/i)).toBeInTheDocument();
		});

		confirmSpy.mockRestore();
	});

	it('does not record cash payment when confirm is cancelled', async () => {
		vi.mocked(billingApi.getAdminOpenPerformanceBills).mockResolvedValue([
			{
				id: 3,
				user_id: 1,
				user_email: 'u@test.com',
				bill_month: '2026-04-01',
				generated_at: '2026-04-30T12:00:00',
				due_at: '2026-05-15T12:00:00',
				status: 'pending_payment',
				payable_amount: 10,
				fee_amount: 10,
				chargeable_profit: 100,
				current_month_pnl: 100,
				previous_carry_forward_loss: 0,
				new_carry_forward_loss: 0,
				fee_percentage: 10,
				paid_at: null,
				razorpay_order_id: null,
			},
		] as never);
		const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

		render(withProviders(<AdminBillingPage />));
		await waitFor(() =>
			expect(screen.getByRole('heading', { name: 'Record cash payment' })).toBeInTheDocument()
		);
		fireEvent.click(screen.getByRole('button', { name: 'Load open bills' }));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Mark paid' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Mark paid' }));

		expect(billingApi.recordAdminCashPayment).not.toHaveBeenCalled();
		confirmSpy.mockRestore();
	});

	it('shows empty message when no open bills after load', async () => {
		vi.mocked(billingApi.getAdminOpenPerformanceBills).mockResolvedValue([]);

		render(withProviders(<AdminBillingPage />));
		await waitFor(() =>
			expect(screen.getByRole('heading', { name: 'Record cash payment' })).toBeInTheDocument()
		);
		fireEvent.click(screen.getByRole('button', { name: 'Load open bills' }));

		await waitFor(() => {
			expect(screen.getByText(/No open performance bills/i)).toBeInTheDocument();
		});
	});

	it('shows error when cash payment fails', async () => {
		vi.mocked(billingApi.getAdminOpenPerformanceBills).mockResolvedValue([
			{
				id: 9,
				user_id: 2,
				user_email: 'u2@test.com',
				bill_month: '2026-05-01',
				generated_at: '2026-05-31T12:00:00',
				due_at: '2026-06-15T12:00:00',
				status: 'overdue',
				payable_amount: 5,
				fee_amount: 5,
				chargeable_profit: 50,
				current_month_pnl: 50,
				previous_carry_forward_loss: 0,
				new_carry_forward_loss: 0,
				fee_percentage: 10,
				paid_at: null,
				razorpay_order_id: null,
			},
		] as never);
		vi.mocked(billingApi.recordAdminCashPayment).mockRejectedValue({
			response: { data: { detail: 'Bill already paid' } },
		});
		vi.spyOn(window, 'confirm').mockReturnValue(true);

		render(withProviders(<AdminBillingPage />));
		await waitFor(() =>
			expect(screen.getByRole('heading', { name: 'Record cash payment' })).toBeInTheDocument()
		);
		fireEvent.click(screen.getByRole('button', { name: 'Load open bills' }));
		await waitFor(() => expect(screen.getByRole('button', { name: 'Mark paid' })).toBeInTheDocument());
		fireEvent.click(screen.getByRole('button', { name: 'Mark paid' }));

		await waitFor(() => {
			expect(screen.getByText('Bill already paid')).toBeInTheDocument();
		});
	});

	it('uploads offline payment QR image', async () => {
		vi.mocked(billingApi.uploadAdminOfflinePaymentQr).mockResolvedValue({
			ok: true,
			offline_payment_qr_uploaded: true,
		} as never);

		render(withProviders(<AdminBillingPage />));
		await waitFor(() =>
			expect(screen.getByRole('button', { name: 'Upload QR image' })).toBeInTheDocument()
		);

		const file = new File(['png-bytes'], 'qr.png', { type: 'image/png' });
		const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
		fireEvent.change(fileInput, { target: { files: [file] } });

		await waitFor(() => {
			expect(billingApi.uploadAdminOfflinePaymentQr).toHaveBeenCalledWith(file);
			expect(screen.getByText('QR image uploaded.')).toBeInTheDocument();
		});
	});

	it('shows uploaded QR preview and removes it', async () => {
		vi.mocked(billingApi.getAdminBillingSettings).mockResolvedValue({
			payment_card_enabled: true,
			payment_upi_enabled: false,
			online_payments_enabled: false,
			offline_payment_upi_id: 'beta@paytm',
			offline_payment_instructions: 'Pay exact amount',
			offline_payment_qr_image_url: null,
			offline_payment_qr_uploaded: true,
			razorpay_key_id_preview: 'rzp_test',
			razorpay_api_configured: true,
			razorpay_webhook_configured: false,
		} as never);
		vi.mocked(billingApi.fetchOfflinePaymentQrBlob).mockResolvedValue(
			new Blob(['preview'], { type: 'image/png' })
		);
		vi.mocked(billingApi.deleteAdminOfflinePaymentQr).mockResolvedValue({
			ok: true,
			offline_payment_qr_uploaded: false,
		} as never);

		render(withProviders(<AdminBillingPage />));

		await waitFor(() => {
			expect(screen.getByRole('button', { name: 'Remove uploaded QR' })).toBeInTheDocument();
			expect(screen.getByAltText('Uploaded payment QR preview')).toBeInTheDocument();
		});

		fireEvent.click(screen.getByRole('button', { name: 'Remove uploaded QR' }));

		await waitFor(() => {
			expect(billingApi.deleteAdminOfflinePaymentQr).toHaveBeenCalled();
			expect(screen.getByText('Uploaded QR removed.')).toBeInTheDocument();
		});
	});

	it('updates razorpay clear flags and refund form fields', async () => {
		render(withProviders(<AdminBillingPage />));
		await waitFor(() => expect(screen.getByText('Refund')).toBeInTheDocument());

		fireEvent.click(screen.getByLabelText(/Clear stored Key ID/i));
		fireEvent.click(screen.getByLabelText(/Clear stored API secret/i));
		fireEvent.click(screen.getByLabelText(/Clear stored webhook secret/i));

		const refundSection = screen.getByText('Refund').closest('section') as HTMLElement;
		const inputs = within(refundSection).getAllByRole('textbox');
		fireEvent.change(inputs[1], { target: { value: '5000' } });
		fireEvent.change(inputs[2], { target: { value: 'Customer request' } });

		const secretInputs = screen.getAllByPlaceholderText('Leave blank to keep stored value');
		fireEvent.change(secretInputs[0], { target: { value: 'secret' } });
		fireEvent.change(secretInputs[1], { target: { value: 'whsec_test' } });
		fireEvent.click(screen.getByRole('button', { name: 'Save Razorpay credentials' }));

		await waitFor(() => {
			expect(billingApi.patchAdminRazorpayCredentials).toHaveBeenCalled();
		});
	});
});
