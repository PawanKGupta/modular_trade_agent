import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
	checkoutPerformanceBill,
	createRazorpayOrder,
	getBillingPaymentOptions,
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

const RAZORPAY_TEST_MODE_MSG =
	'Razorpay is in TEST mode. Do not scan the QR with a real UPI app — verification will fail. ' +
	'In checkout: open UPI, choose “UPI ID / VPA”, enter success@razorpay, and pay. ' +
	'Or use Razorpay test cards. For real QR/UPI, set rzp_live_ keys on the server.';

function razorpayTestModeMessage(testMode?: boolean): string | null {
	return testMode ? RAZORPAY_TEST_MODE_MSG : null;
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

function OfflinePaymentPanel({
	upiId,
	instructions,
	qrUrl,
	bill,
}: {
	upiId: string | null;
	instructions: string | null;
	qrUrl: string | null;
	bill?: PerformanceBill;
}) {
	const hasBill = bill && (bill.status === 'pending_payment' || bill.status === 'overdue') && bill.payable_amount > 0;
	return (
		<div className="mt-2 p-3 rounded bg-[#0f1720] border border-amber-900/40 space-y-2 text-xs">
			<p className="text-amber-200/90 font-medium">Pay via UPI</p>
			<p className="text-[var(--muted)] leading-relaxed">
				Pay the exact amount below. We’ll mark your bill paid after confirmation.
			</p>
			{hasBill ? (
				<p className="text-sm">
					Amount: <span className="font-medium text-[var(--text)]">₹{bill.payable_amount.toFixed(2)}</span>
					<span className="text-[var(--muted)]"> · Bill #{bill.id}</span>
				</p>
			) : null}
			{upiId ? (
				<p>
					UPI ID:{' '}
					<code className="text-amber-100 bg-[#1e293b] px-1.5 py-0.5 rounded select-all">{upiId}</code>
				</p>
			) : null}
			{qrUrl ? (
				<div className="space-y-1">
					<p className="text-[var(--muted)]">Scan QR</p>
					<img
						src={qrUrl}
						alt="Payment QR code"
						className="max-w-[12rem] rounded border border-[#1e293b] bg-white p-1"
					/>
				</div>
			) : null}
			{instructions ? (
				<p className="text-[var(--muted)] whitespace-pre-wrap leading-relaxed">{instructions}</p>
			) : (
				<p className="text-[var(--muted)]">Add bill # and email in the UPI note.</p>
			)}
		</div>
	);
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

	const paymentOptsQ = useQuery({
		queryKey: ['billingPaymentOptions'],
		queryFn: getBillingPaymentOptions,
	});
	const onlinePay = paymentOptsQ.data?.online_payments_enabled ?? false;

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
				const testModeMsg = razorpayTestModeMessage(data.razorpay_test_mode);
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
				(rzp as unknown as { on?: (ev: string, cb: (r: unknown) => void) => void }).on?.(
					'payment.failed',
					(r) => {
						const base = testModeMsg ? `${testModeMsg}\n\n` : '';
						setMsg(`${base}Payment failed: ${JSON.stringify(r)}`);
					}
				);
				setMsg(testModeMsg);
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
				const testModeMsg = razorpayTestModeMessage(o.razorpay_test_mode ?? o.key_id.startsWith('rzp_test_'));
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
				setMsg(testModeMsg);
				(rzp as unknown as { on?: (ev: string, cb: (r: unknown) => void) => void }).on?.(
					'payment.failed',
					(r) => {
						const base = testModeMsg ? `${testModeMsg}\n\n` : '';
						setMsg(`${base}Payment failed: ${JSON.stringify(r)}`);
					}
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

	const offlineUpi = paymentOptsQ.data?.offline_upi_id ?? null;
	const offlineInstructions = paymentOptsQ.data?.offline_instructions ?? null;
	const offlineQr = paymentOptsQ.data?.offline_qr_image_url ?? null;

	return (
		<div className="p-4 sm:p-6 max-w-4xl space-y-6 text-[var(--text)]">
			<div>
				<h1 className="text-xl font-semibold">Billing</h1>
				<p className="text-sm text-[var(--muted)] mt-1 max-w-2xl">
					Broker performance fee invoices and payment history for this account.
					{onlinePay ? ' Pay open invoices online via Razorpay.' : ' Pay via UPI below.'}
				</p>
			</div>

			{!onlinePay && !paymentOptsQ.isLoading ? (
				<OfflinePaymentPanel
					upiId={offlineUpi}
					instructions={offlineInstructions}
					qrUrl={offlineQr}
				/>
			) : null}

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
						{isAdmin && onlinePay ? (
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
						{(perfBillsQ.data ?? []).map((b: PerformanceBill) => {
							const unpaid =
								(b.status === 'pending_payment' || b.status === 'overdue') && b.payable_amount > 0;
							return (
								<li
									key={b.id}
									className="flex flex-col gap-2 p-2 rounded bg-[#0f1720] border border-[#1e293b]/80"
								>
									<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
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
										{unpaid && onlinePay ? (
											<button
												type="button"
												className="px-3 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-sm self-start sm:self-center disabled:opacity-40"
												disabled={perfPayM.isPending}
												onClick={() => perfPayM.mutate(b.id)}
											>
												Pay now (online)
											</button>
										) : null}
									</div>
									{unpaid && !onlinePay ? (
										<OfflinePaymentPanel
											upiId={offlineUpi}
											instructions={offlineInstructions}
											qrUrl={offlineQr}
											bill={b}
										/>
									) : null}
								</li>
							);
						})}
					</ul>
				)}
			</section>

			{showTestCheckout && onlinePay ? (
				<section className="p-4 rounded border border-[#1e293b] space-y-3">
					<div>
						<h2 className="font-medium">Dev — Test Razorpay checkout</h2>
						<p className="text-xs text-[var(--muted)]">
							Creates a generic Razorpay order and verifies the callback signature server-side. Minimum 100
							paise.
						</p>
						<p className="text-xs text-amber-300/90 mt-1">
							With test keys (rzp_test_*), never scan the checkout QR with PhonePe/GPay/Paytm — use UPI ID{' '}
							<code className="text-amber-200">success@razorpay</code> inside the modal instead.
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
