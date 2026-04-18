import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
	cancelSubscription,
	changePlan,
	getBillingPlans,
	getEntitlements,
	getMyBillingTransactions,
	getMySubscription,
	getSubscriptionPayLink,
	subscribeCheckout,
	type BillingPlan,
	type Entitlements,
} from '@/api/billing';

const FEATURE_LABELS: Record<string, string> = {
	stock_recommendations: 'Stock recommendations',
	broker_execution: 'Broker execution',
	auto_trade_services: 'Auto trade services',
	paper_trading: 'Paper trading',
};

function formatPlanTier(tier: string | null): string {
	if (!tier) return '—';
	return tier.replace(/_/g, ' ');
}

function formatEntitlementStatus(status: string | null): string {
	if (!status) return '—';
	if (status === 'enforcement_off') return 'Full access (billing enforcement off)';
	return status.replace(/_/g, ' ');
}

function EntitlementsCard({ e }: { e: Entitlements }) {
	const featureEntries = Object.entries(e.features ?? {});
	return (
		<div className="rounded bg-[#0f1720] border border-[#1e293b] p-3 space-y-3 text-sm">
			<div className="flex flex-wrap gap-x-6 gap-y-2">
				<div>
					<p className="text-xs text-[var(--muted)]">Access</p>
					<p className="font-medium">{e.active ? 'Active' : 'Inactive'}</p>
				</div>
				<div>
					<p className="text-xs text-[var(--muted)]">Billing status</p>
					<p className="font-medium">{formatEntitlementStatus(e.status)}</p>
				</div>
				<div>
					<p className="text-xs text-[var(--muted)]">Plan tier</p>
					<p className="font-medium capitalize">{formatPlanTier(e.plan_tier)}</p>
				</div>
				<div>
					<p className="text-xs text-[var(--muted)]">Current period ends</p>
					<p className="font-medium">{e.current_period_end ?? '—'}</p>
				</div>
			</div>
			<div>
				<p className="text-xs text-[var(--muted)] mb-2">Included capabilities</p>
				<ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
					{featureEntries.length ? (
						featureEntries.map(([key, on]) => (
							<li key={key} className="flex items-center justify-between gap-2 py-1 border-b border-[#1e293b]/40 last:border-0">
								<span>{FEATURE_LABELS[key] ?? key.replace(/_/g, ' ')}</span>
								<span className={on ? 'text-emerald-400' : 'text-[var(--muted)]'}>{on ? 'Yes' : 'No'}</span>
							</li>
						))
					) : (
						<li className="text-[var(--muted)]">No feature flags returned.</li>
					)}
				</ul>
			</div>
		</div>
	);
}

declare global {
	interface Window {
		Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
	}
}

function loadRazorpayScript(): Promise<void> {
	if (typeof window === 'undefined') return Promise.resolve();
	if (window.Razorpay) return Promise.resolve();
	return new Promise((resolve, reject) => {
		const s = document.createElement('script');
		s.src = 'https://checkout.razorpay.com/v1/checkout.js';
		s.async = true;
		s.onload = () => resolve();
		s.onerror = () => reject(new Error('Failed to load Razorpay Checkout script'));
		document.body.appendChild(s);
	});
}

export function BillingPage() {
	const qc = useQueryClient();
	const [coupon, setCoupon] = useState('');
	const [msg, setMsg] = useState<string | null>(null);

	const plansQ = useQuery({ queryKey: ['billingPlans'], queryFn: getBillingPlans });
	const entQ = useQuery({ queryKey: ['entitlements'], queryFn: getEntitlements });
	const subQ = useQuery({ queryKey: ['mySubscription'], queryFn: getMySubscription });
	const txQ = useQuery({ queryKey: ['billingTx'], queryFn: () => getMyBillingTransactions(50) });

	const subscribeM = useMutation({
		mutationFn: (planId: number) =>
			subscribeCheckout({ plan_id: planId, coupon_code: coupon.trim() || null }),
		onSuccess: async (data) => {
			void qc.invalidateQueries({ queryKey: ['mySubscription'] });
			void qc.invalidateQueries({ queryKey: ['entitlements'] });
			if (data.razorpay_key_id && data.razorpay_subscription_id) {
				try {
					await loadRazorpayScript();
					const Ctor = window.Razorpay;
					if (!Ctor) {
						setMsg('Razorpay script loaded but constructor missing.');
						return;
					}
					const rzp = new Ctor({
						key: data.razorpay_key_id,
						subscription_id: data.razorpay_subscription_id,
						name: 'Rebound',
						description: 'Subscription checkout',
						handler() {
							setMsg('Payment completed.');
							void qc.invalidateQueries({ queryKey: ['mySubscription'] });
							void qc.invalidateQueries({ queryKey: ['entitlements'] });
							void qc.invalidateQueries({ queryKey: ['billingTx'] });
						},
						modal: {
							ondismiss() {
								setMsg('Checkout closed before completion.');
							},
						},
					});
					setMsg(null);
					rzp.open();
				} catch (e) {
					setMsg(e instanceof Error ? e.message : 'Checkout failed to open');
				}
			} else if (data.amount_quoted_paise <= 0) {
				setMsg('Subscription is active — no payment required for this plan.');
			} else {
				setMsg(
					`Subscription row created (#${data.user_subscription_id}) but Razorpay is not configured — complete payment in the Razorpay dashboard.`
				);
			}
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setMsg(d ?? 'Subscribe failed');
		},
	});

	const payLinkM = useMutation({
		mutationFn: getSubscriptionPayLink,
		onSuccess: (d) => {
			if (d.short_url) {
				window.open(d.short_url, '_blank', 'noopener,noreferrer');
				setMsg('Opened Razorpay payment page in a new tab.');
			} else {
				setMsg(d.detail ?? 'No hosted payment link available right now.');
			}
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setMsg(d ?? 'Could not load pay link');
		},
	});

	const cancelM = useMutation({
		mutationFn: cancelSubscription,
		onSuccess: () => {
			setMsg('Cancellation recorded.');
			void qc.invalidateQueries({ queryKey: ['mySubscription'] });
		},
	});

	const changeM = useMutation({
		mutationFn: ({ sid, pid }: { sid: number; pid: number }) => changePlan(sid, pid),
		onSuccess: () => {
			setMsg('Plan change scheduled for next billing cycle (applied on renewal charge).');
			void qc.invalidateQueries({ queryKey: ['mySubscription'] });
		},
	});

	const sub = subQ.data;

	return (
		<div className="p-4 sm:p-6 max-w-4xl space-y-6 text-[var(--text)]">
			<h1 className="text-xl font-semibold">Subscription & billing</h1>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Current access</h2>
				{entQ.isLoading ? (
					<p className="text-sm text-[var(--muted)]">Loading…</p>
				) : entQ.data ? (
					<EntitlementsCard e={entQ.data} />
				) : (
					<p className="text-sm text-[var(--muted)]">No entitlement data.</p>
				)}
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Active subscription</h2>
				{subQ.isLoading ? (
					<p className="text-sm text-[var(--muted)]">Loading…</p>
				) : sub ? (
					<div className="text-sm space-y-2">
						<p>
							Status: <strong>{sub.status}</strong> — Plan #{sub.plan_id}
						</p>
						<p className="text-[var(--muted)]">Renews: {sub.current_period_end ?? '—'}</p>
						{sub.trial_end ? (
							<p className="text-[var(--muted)]">Trial ends: {sub.trial_end}</p>
						) : null}
						{sub.pending_plan_id ? (
							<p className="text-amber-300 text-xs">
								Pending plan change to #{sub.pending_plan_id} (applied on next renewal charge).
							</p>
						) : null}
						<div className="flex flex-wrap gap-2">
							<button
								type="button"
								className="px-3 py-1.5 rounded bg-slate-600 hover:bg-slate-500 text-white text-sm"
								onClick={() => payLinkM.mutate()}
								disabled={payLinkM.isPending}
							>
								Open Razorpay pay / retry
							</button>
							<button
								type="button"
								className="px-3 py-1.5 rounded bg-amber-700 hover:bg-amber-600 text-white text-sm"
								onClick={() => cancelM.mutate(sub.id)}
								disabled={cancelM.isPending}
							>
								Cancel at period end
							</button>
						</div>
					</div>
				) : (
					<p className="text-sm text-[var(--muted)]">No subscription record yet.</p>
				)}
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-3">
				<h2 className="font-medium">Plans</h2>
				<div className="flex gap-2 items-center">
					<input
						value={coupon}
						onChange={(e) => setCoupon(e.target.value)}
						placeholder="Coupon code (optional)"
						className="flex-1 min-w-[8rem] px-2 py-1.5 rounded bg-[#0f1720] border border-[#1e293b] text-sm"
					/>
				</div>
				{plansQ.isLoading ? (
					<p className="text-sm text-[var(--muted)]">Loading plans…</p>
				) : (
					<ul className="space-y-2">
						{(plansQ.data ?? []).map((p: BillingPlan) => (
							<li
								key={p.id}
								className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 p-3 rounded bg-[#0f1720] border border-[#1e293b]"
							>
								<div>
									<div className="font-medium">{p.name}</div>
									<div className="text-xs text-[var(--muted)]">{p.description}</div>
									<div className="text-xs mt-1">
										₹{(p.effective_amount_paise / 100).toFixed(2)} / {p.billing_interval}
									</div>
								</div>
								<div className="flex flex-wrap gap-2">
									<button
										type="button"
										className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm"
										onClick={() => subscribeM.mutate(p.id)}
										disabled={subscribeM.isPending}
									>
										Subscribe
									</button>
									{sub ? (
										<button
											type="button"
											className="px-3 py-1.5 rounded bg-slate-600 hover:bg-slate-500 text-white text-sm"
											onClick={() => changeM.mutate({ sid: sub.id, pid: p.id })}
											disabled={changeM.isPending}
										>
											Schedule switch
										</button>
									) : null}
								</div>
							</li>
						))}
					</ul>
				)}
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Billing history</h2>
				{txQ.isLoading ? (
					<p className="text-sm text-[var(--muted)]">Loading…</p>
				) : (
					<ul className="text-sm space-y-1 max-h-64 overflow-auto">
						{(txQ.data ?? []).map((t) => (
							<li key={t.id} className="flex justify-between gap-2 border-b border-[#1e293b]/50 py-1">
								<span>{t.status}</span>
								<span className="text-[var(--muted)]">₹{(t.amount_paise / 100).toFixed(2)}</span>
								<span className="text-xs text-[var(--muted)]">{t.created_at}</span>
							</li>
						))}
					</ul>
				)}
			</section>

			{msg ? <p className="text-sm text-amber-300 whitespace-pre-wrap">{msg}</p> : null}
		</div>
	);
}
