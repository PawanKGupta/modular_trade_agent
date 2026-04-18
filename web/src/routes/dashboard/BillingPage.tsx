import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
	checkoutPerformanceBill,
	getMyBillingTransactions,
	getPerformanceBills,
	type PerformanceBill,
} from '@/api/billing';

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
	const [msg, setMsg] = useState<string | null>(null);

	const txQ = useQuery({ queryKey: ['billingTx'], queryFn: () => getMyBillingTransactions(50) });
	const perfBillsQ = useQuery({ queryKey: ['performanceBills'], queryFn: () => getPerformanceBills(36) });

	const perfPayM = useMutation({
		mutationFn: (billId: number) => checkoutPerformanceBill(billId),
		onSuccess: async (data) => {
			try {
				await loadRazorpayScript();
				const Ctor = window.Razorpay;
				if (!Ctor || !data.razorpay_key_id || !data.order_id) {
					setMsg('Razorpay is not available or checkout data is incomplete.');
					return;
				}
				const rzp = new Ctor({
					key: data.razorpay_key_id,
					amount: data.amount_paise,
					currency: data.currency,
					order_id: data.order_id,
					name: 'Rebound',
					description: 'Broker performance fee',
					handler() {
						setMsg('Payment submitted — history will refresh shortly.');
						void qc.invalidateQueries({ queryKey: ['performanceBills'] });
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
				setMsg(e instanceof Error ? e.message : 'Performance fee checkout failed');
			}
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setMsg(d ?? 'Could not start performance fee payment');
		},
	});

	return (
		<div className="p-4 sm:p-6 max-w-4xl space-y-6 text-[var(--text)]">
			<div>
				<h1 className="text-xl font-semibold">Billing</h1>
				<p className="text-sm text-[var(--muted)] mt-1 max-w-2xl">
					Broker performance fee invoices and your Razorpay payment history for this account.
				</p>
			</div>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Broker performance fees</h2>
				<p className="text-xs text-[var(--muted)]">
					Monthly invoices when you trade on a live broker. Amounts use the same unit as your realized PnL.
				</p>
				{perfBillsQ.isLoading ? (
					<p className="text-sm text-[var(--muted)]">Loading…</p>
				) : (perfBillsQ.data ?? []).length === 0 ? (
					<p className="text-sm text-[var(--muted)]">No performance fee bills yet.</p>
				) : (
					<ul className="text-sm space-y-2 max-h-72 overflow-auto">
						{(perfBillsQ.data ?? []).map((b: PerformanceBill) => (
							<li
								key={b.id}
								className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 p-2 rounded bg-[#0f1720] border border-[#1e293b]/80"
							>
								<div>
									<p className="font-medium">
										{b.bill_month} — {b.status.replace(/_/g, ' ')}
									</p>
									<p className="text-xs text-[var(--muted)]">
										Due {b.due_at.slice(0, 10)}
										{b.paid_at ? ` · Paid ${b.paid_at.slice(0, 10)}` : ''}
									</p>
									<p className="text-xs text-[var(--muted)] mt-1">
										PnL {b.current_month_pnl.toFixed(2)} · Fee {b.fee_percentage}% · Payable ₹
										{b.payable_amount.toFixed(2)}
									</p>
								</div>
								{(b.status === 'pending_payment' || b.status === 'overdue') && b.payable_amount > 0 ? (
									<button
										type="button"
										className="px-3 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-sm self-start sm:self-center disabled:opacity-40"
										disabled={perfPayM.isPending}
										onClick={() => perfPayM.mutate(b.id)}
									>
										Pay now
									</button>
								) : null}
							</li>
						))}
					</ul>
				)}
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Payment history</h2>
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
