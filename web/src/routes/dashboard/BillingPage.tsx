import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
	checkoutPerformanceBill,
	createRazorpayOrder,
	getMyBillingTransactions,
	getPerformanceBills,
	verifyRazorpayPayment,
	type PerformanceBill,
} from '@/api/billing';
import { useSessionStore } from '@/state/sessionStore';

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
	const { isAdmin } = useSessionStore();
	const [msg, setMsg] = useState<string | null>(null);
	const [testAmountPaise, setTestAmountPaise] = useState<number>(100);
	const [testCheckoutOpen, setTestCheckoutOpen] = useState<boolean>(false);
	const showTestCheckout =
		isAdmin &&
		(testCheckoutOpen ||
			(typeof window !== 'undefined' &&
				(new URLSearchParams(window.location.search).has('testCheckout') ||
					import.meta.env.DEV)));

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
					handler(razorResponse: {
						razorpay_payment_id: string;
						razorpay_order_id: string;
						razorpay_signature: string;
					}) {
						void (async () => {
							try {
								const v = await verifyRazorpayPayment({
									razorpay_order_id: razorResponse.razorpay_order_id,
									razorpay_payment_id: razorResponse.razorpay_payment_id,
									razorpay_signature: razorResponse.razorpay_signature,
									performance_bill_id: data.bill_id,
								});
								if (v.verified) {
									setMsg('Payment verified — settlement may take a moment; history will refresh shortly.');
									void qc.invalidateQueries({ queryKey: ['performanceBills'] });
									void qc.invalidateQueries({ queryKey: ['billingTx'] });
									void qc.invalidateQueries({ queryKey: ['performanceFeeArrears'] });
								} else {
									setMsg(v.detail || 'Could not verify payment with server.');
								}
							} catch (err) {
								const d = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
								setMsg(
									typeof d === 'string'
										? d
										: d
											? JSON.stringify(d)
											: 'Payment verification failed. Webhooks may still update your bill.'
								);
							}
						})();
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
			const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
			setMsg(typeof d === 'string' ? d : d ? JSON.stringify(d) : 'Could not start performance fee payment');
		},
	});

	const testPayM = useMutation({
		mutationFn: async (amount_paise: number) => {
			const amt = Math.max(100, Math.floor(amount_paise));
			return await createRazorpayOrder({ amount_paise: amt, currency: 'INR', receipt: null });
		},
		onSuccess: async (o) => {
			try {
				await loadRazorpayScript();
				const Ctor = window.Razorpay;
				if (!Ctor || !o.key_id || !o.order_id) {
					setMsg('Razorpay is not available or checkout data is incomplete.');
					return;
				}
				const rzp = new Ctor({
					key: o.key_id,
					amount: o.amount,
					currency: o.currency,
					order_id: o.order_id,
					name: 'Rebound',
					description: 'Test payment (Standard Checkout)',
					handler(razorResponse: {
						razorpay_payment_id: string;
						razorpay_order_id: string;
						razorpay_signature: string;
					}) {
						void (async () => {
							try {
								const v = await verifyRazorpayPayment({
									razorpay_order_id: razorResponse.razorpay_order_id,
									razorpay_payment_id: razorResponse.razorpay_payment_id,
									razorpay_signature: razorResponse.razorpay_signature,
								});
								setMsg(v.verified ? 'Test payment verified.' : v.detail || 'Could not verify payment.');
								void qc.invalidateQueries({ queryKey: ['billingTx'] });
							} catch (err) {
								const d = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
								setMsg(typeof d === 'string' ? d : d ? JSON.stringify(d) : 'Test payment verification failed.');
							}
						})();
					},
					modal: {
						ondismiss() {
							setMsg('Checkout closed before completion.');
						},
					},
				});
				setMsg(null);
				(rzp as unknown as { on?: (ev: string, cb: (r: unknown) => void) => void }).on?.(
					'payment.failed',
					(r) => setMsg(`Payment failed: ${JSON.stringify(r)}`)
				);
				rzp.open();
			} catch (e) {
				setMsg(e instanceof Error ? e.message : 'Test checkout failed');
			}
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
			setMsg(typeof d === 'string' ? d : d ? JSON.stringify(d) : 'Could not create Razorpay order');
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
					<div className="space-y-2">
						<p className="text-sm text-[var(--muted)]">No performance fee bills yet.</p>
						{isAdmin ? (
							<button
								type="button"
								className="px-3 py-2 rounded bg-indigo-700 hover:bg-indigo-600 text-white text-sm disabled:opacity-40"
								onClick={() => setTestCheckoutOpen(true)}
							>
								Test Razorpay checkout
							</button>
						) : null}
					</div>
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

			{showTestCheckout ? (
				<section className="p-4 rounded border border-[#1e293b] space-y-3">
					<div>
						<h2 className="font-medium">Dev — Test Razorpay checkout</h2>
						<p className="text-xs text-[var(--muted)]">
							Creates a generic Razorpay order and verifies the callback signature server-side. Minimum 100 paise.
						</p>
					</div>
					<div className="flex flex-col sm:flex-row gap-2 sm:items-end">
						<label className="text-sm">
							<span className="block text-xs text-[var(--muted)]">Amount (paise)</span>
							<input
								className="mt-1 px-3 py-2 rounded bg-[#0f1720] border border-[#1e293b] text-sm w-40"
								type="number"
								min={100}
								step={1}
								value={testAmountPaise}
								onChange={(e) => setTestAmountPaise(Number(e.target.value || 0))}
							/>
						</label>
						<button
							type="button"
							className="px-3 py-2 rounded bg-indigo-700 hover:bg-indigo-600 text-white text-sm disabled:opacity-40"
							disabled={testPayM.isPending}
							onClick={() => testPayM.mutate(testAmountPaise)}
						>
							Pay (test)
						</button>
					</div>
				</section>
			) : null}

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
