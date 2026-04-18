import { api } from './client';

export type BillingPlan = {
	id: number;
	slug: string;
	name: string;
	description: string | null;
	plan_tier: string;
	billing_interval: string;
	base_amount_paise: number;
	effective_amount_paise: number;
	currency: string;
	features_json: Record<string, boolean>;
	razorpay_plan_id: string | null;
	is_active: boolean;
};

export type Entitlements = {
	active: boolean;
	status: string | null;
	plan_tier: string | null;
	features: Record<string, boolean>;
	current_period_end: string | null;
};

export type UserSubscription = {
	id: number;
	plan_id: number;
	status: string;
	billing_provider: string;
	started_at: string | null;
	current_period_end: string | null;
	cancel_at_period_end: boolean;
	trial_end: string | null;
	pending_plan_id: number | null;
};

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

export async function getBillingPlans(): Promise<BillingPlan[]> {
	const res = await api.get<BillingPlan[]>('/user/billing/plans');
	return res.data;
}

export async function getEntitlements(): Promise<Entitlements> {
	const res = await api.get<Entitlements>('/user/billing/entitlements');
	return res.data;
}

export async function getMySubscription(): Promise<UserSubscription | null> {
	const res = await api.get<UserSubscription | null>('/user/billing/subscription');
	return res.data;
}

export async function subscribeCheckout(input: {
	plan_id: number;
	coupon_code?: string | null;
}): Promise<{
	razorpay_key_id: string | null;
	razorpay_subscription_id: string | null;
	user_subscription_id: number;
	amount_quoted_paise: number;
	trial_days_applied: number;
}> {
	const res = await api.post('/user/billing/subscribe', input);
	return res.data;
}

export async function cancelSubscription(userSubscriptionId: number): Promise<UserSubscription> {
	const res = await api.post('/user/billing/cancel', null, {
		params: { user_subscription_id: userSubscriptionId },
	});
	return res.data;
}

export async function changePlan(userSubscriptionId: number, newPlanId: number): Promise<UserSubscription> {
	const res = await api.post('/user/billing/change-plan', null, {
		params: { user_subscription_id: userSubscriptionId, new_plan_id: newPlanId },
	});
	return res.data;
}

export async function getMyBillingTransactions(limit = 100): Promise<BillingTransaction[]> {
	const res = await api.get<BillingTransaction[]>('/user/billing/transactions', { params: { limit } });
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

export async function getAdminBillingPlans(): Promise<BillingPlan[]> {
	const res = await api.get<BillingPlan[]>('/admin/billing/plans');
	return res.data;
}

export async function getAdminSubscriptions(limit = 200): Promise<UserSubscription[]> {
	const res = await api.get<UserSubscription[]>('/admin/billing/subscriptions', { params: { limit } });
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

export async function getBillingReports(year: number, month: number): Promise<Record<string, unknown>> {
	const res = await api.get('/admin/billing/reports', { params: { year, month } });
	return res.data;
}

export async function runBillingReconcile(): Promise<Record<string, unknown>> {
	const res = await api.post('/admin/billing/reconcile');
	return res.data;
}
