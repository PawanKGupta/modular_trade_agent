import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
	cancelSubscription,
	changePlan,
	getBillingPlans,
	getEntitlements,
	getMyBillingTransactions,
	getMySubscription,
	subscribeCheckout,
	type BillingPlan,
} from '@/api/billing';

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
		onSuccess: (data) => {
			setMsg(
				`Checkout created. Use Razorpay Checkout with subscription_id=${data.razorpay_subscription_id ?? 'n/a'} (key_id=${data.razorpay_key_id ?? 'n/a'}).`
			);
			void qc.invalidateQueries({ queryKey: ['mySubscription'] });
			void qc.invalidateQueries({ queryKey: ['entitlements'] });
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setMsg(d ?? 'Subscribe failed');
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
			setMsg('Plan change scheduled for next cycle.');
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
				) : (
					<pre className="text-xs overflow-auto bg-[#0f1720] p-3 rounded">
						{JSON.stringify(ent, null, 2)}
					</pre>
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
						<div className="flex flex-wrap gap-2">
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
