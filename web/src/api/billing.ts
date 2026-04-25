import { api } from './client';

export type BillingTransaction = {
	id: number;
	user_id: number;
	user_subscription_id: number | null;
	amount_paise: number;
	currency: string;
	status: string;
	razorpay_payment_id: string | null;
	failure_reason: string | null;
	created_at: string;
};

export async function getMyBillingTransactions(limit = 100): Promise<BillingTransaction[]> {
	const res = await api.get<BillingTransaction[]>('/user/billing/transactions', { params: { limit } });
	return res.data;
}

export type PerformanceFeeArrearBill = {
	id: number;
	bill_month: string;
	due_at: string;
	payable_amount: number;
	status: string;
};

export type PerformanceFeeArrears = {
	blocks_new_broker_buys: boolean;
	message: string | null;
	bills: PerformanceFeeArrearBill[];
};

export async function getPerformanceFeeArrears(): Promise<PerformanceFeeArrears> {
	const res = await api.get<PerformanceFeeArrears>('/user/billing/performance-fee-arrears');
	return res.data;
}

export type PerformanceBill = {
	id: number;
	bill_month: string;
	generated_at: string;
	due_at: string;
	status: string;
	payable_amount: number;
	fee_amount: number;
	chargeable_profit: number;
	current_month_pnl: number;
	previous_carry_forward_loss: number;
	new_carry_forward_loss: number;
	fee_percentage: number;
	paid_at: string | null;
	razorpay_order_id: string | null;
};

export async function getPerformanceBills(limit = 36): Promise<PerformanceBill[]> {
	const res = await api.get<PerformanceBill[]>('/user/billing/performance-bills', { params: { limit } });
	return res.data;
}

export type PerformanceFeeCheckout = {
	razorpay_key_id: string;
	order_id: string;
	amount_paise: number;
	currency: string;
	bill_id: number;
};

export async function checkoutPerformanceBill(billId: number): Promise<PerformanceFeeCheckout> {
	const res = await api.post<PerformanceFeeCheckout>(`/user/billing/performance-bills/${billId}/checkout`);
	return res.data;
}

/** Standard Checkout: generic order (e.g. integration tests / playground). Min 100 paise. */
export type RazorpayCreateOrderResponse = {
	order_id: string;
	amount: number;
	currency: string;
	key_id: string;
};

export async function createRazorpayOrder(body: {
	amount_paise: number;
	currency?: string;
	receipt?: string | null;
}): Promise<RazorpayCreateOrderResponse> {
	const res = await api.post<RazorpayCreateOrderResponse>('/user/billing/razorpay/create-order', body);
	return res.data;
}

export type RazorpayVerifyPaymentResponse = { verified: boolean; detail: string | null };

export async function verifyRazorpayPayment(body: {
	razorpay_order_id: string;
	razorpay_payment_id: string;
	razorpay_signature: string;
	performance_bill_id?: number | null;
}): Promise<RazorpayVerifyPaymentResponse> {
	const res = await api.post<RazorpayVerifyPaymentResponse>('/user/billing/razorpay/verify-payment', body);
	return res.data;
}

/** Admin */
export async function getAdminBillingSettings(): Promise<Record<string, unknown>> {
	const res = await api.get('/admin/billing/settings');
	return res.data;
}

export async function patchAdminBillingSettings(
	body: Record<string, unknown>
): Promise<Record<string, unknown>> {
	const res = await api.patch('/admin/billing/settings', body);
	return res.data;
}

/** PATCH /admin/billing/razorpay-credentials — partial update; null clears stored DB value. */
export async function patchAdminRazorpayCredentials(body: Record<string, unknown>): Promise<Record<string, unknown>> {
	const res = await api.patch('/admin/billing/razorpay-credentials', body);
	return res.data;
}

export async function getAdminTransactions(params?: {
	user_id?: number;
	failed_only?: boolean;
	limit?: number;
}): Promise<BillingTransaction[]> {
	const res = await api.get<BillingTransaction[]>('/admin/billing/transactions', { params });
	return res.data;
}

export async function runBillingReconcile(): Promise<Record<string, unknown>> {
	const res = await api.post('/admin/billing/reconcile');
	return res.data;
}

export async function postAdminRefund(body: {
	billing_transaction_id: number;
	amount_paise?: number | null;
	reason?: string | null;
}): Promise<{ ok: boolean }> {
	const res = await api.post<{ ok: boolean }>('/admin/billing/refunds', body);
	return res.data;
}
