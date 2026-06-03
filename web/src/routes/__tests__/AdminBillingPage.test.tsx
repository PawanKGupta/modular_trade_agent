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
}));

describe('AdminBillingPage', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(billingApi.getAdminBillingSettings).mockResolvedValue({
			payment_card_enabled: true,
			payment_upi_enabled: false,
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

		await waitFor(() => expect(screen.getByText('UPI')).toBeInTheDocument());
		const checkboxes = screen.getAllByRole('checkbox');
		const upi = checkboxes.find((cb) => cb.closest('label')?.textContent?.includes('UPI'));
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
