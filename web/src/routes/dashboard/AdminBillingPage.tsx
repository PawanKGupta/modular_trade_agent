import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import {
	deleteAdminOfflinePaymentQr,
	getAdminBillingSettings,
	getAdminOpenPerformanceBills,
	getAdminTransactions,
	patchAdminBillingSettings,
	patchAdminRazorpayCredentials,
	postAdminRefund,
	recordAdminCashPayment,
	runBillingReconcile,
	uploadAdminOfflinePaymentQr,
	type AdminPerformanceBill,
	type BillingTransaction,
	fetchOfflinePaymentQrBlob,
} from '@/api/billing';
import { PasswordInput } from '@/components/PasswordInput';

function formatInrPaise(paise: number): string {
	return `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function TxTable({ rows, empty }: { rows: BillingTransaction[]; empty: string }) {
	if (!rows.length) return <p className="text-sm text-[var(--muted)]">{empty}</p>;
	return (
		<div className="max-h-48 overflow-auto text-xs">
			<table className="w-full border-collapse">
				<thead>
					<tr className="text-left text-[var(--muted)]">
						<th className="p-1">ID</th>
						<th className="p-1">User</th>
						<th className="p-1">Status</th>
						<th className="p-1">Amount</th>
						<th className="p-1">When</th>
					</tr>
				</thead>
				<tbody>
					{rows.map((t) => (
						<tr key={t.id} className="border-t border-[#1e293b]/60">
							<td className="p-1">{t.id}</td>
							<td className="p-1">{t.user_id}</td>
							<td className="p-1">{t.status}</td>
							<td className="p-1">{formatInrPaise(t.amount_paise)}</td>
							<td className="p-1 text-[var(--muted)]">{t.created_at}</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

function OfflinePaymentQrPreview() {
	const [src, setSrc] = useState<string | null>(null);

	useEffect(() => {
		let objectUrl: string | null = null;
		let cancelled = false;
		void fetchOfflinePaymentQrBlob().then((blob) => {
			if (cancelled || !blob) return;
			objectUrl = URL.createObjectURL(blob);
			setSrc(objectUrl);
		});
		return () => {
			cancelled = true;
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		};
	}, []);

	if (!src) return null;
	return (
		<img
			src={src}
			alt="Uploaded payment QR preview"
			className="max-w-[10rem] rounded border border-[#1e293b] bg-white p-1"
		/>
	);
}

export function AdminBillingPage() {
	const qc = useQueryClient();
	const [adminMsg, setAdminMsg] = useState<string | null>(null);

	const [rzKeyId, setRzKeyId] = useState('');
	const [rzKeySecret, setRzKeySecret] = useState('');
	const [rzWebhookSecret, setRzWebhookSecret] = useState('');
	const [rzClearKeyId, setRzClearKeyId] = useState(false);
	const [rzClearKeySecret, setRzClearKeySecret] = useState(false);
	const [rzClearWebhook, setRzClearWebhook] = useState(false);

	const [refundTxId, setRefundTxId] = useState('');
	const [refundAmount, setRefundAmount] = useState('');
	const [refundReason, setRefundReason] = useState('');

	const [cashUserId, setCashUserId] = useState('');
	const [cashNote, setCashNote] = useState('');
	const [cashBillsUserFilter, setCashBillsUserFilter] = useState<number | undefined>(undefined);
	const [openBillsRequested, setOpenBillsRequested] = useState(false);

	const [offlineUpi, setOfflineUpi] = useState('');
	const [offlineInstructions, setOfflineInstructions] = useState('');
	const [offlineQrUrl, setOfflineQrUrl] = useState('');
	const [offlineQrUploaded, setOfflineQrUploaded] = useState(false);
	const qrFileInputRef = useRef<HTMLInputElement>(null);

	const settingsQ = useQuery({ queryKey: ['adminBillingSettings'], queryFn: getAdminBillingSettings });
	const s = settingsQ.data;
	useEffect(() => {
		if (!s) return;
		const row = s as Record<string, unknown>;
		setOfflineUpi(String(row.offline_payment_upi_id ?? ''));
		setOfflineInstructions(String(row.offline_payment_instructions ?? ''));
		setOfflineQrUrl(String(row.offline_payment_qr_image_url ?? ''));
		setOfflineQrUploaded(Boolean(row.offline_payment_qr_uploaded));
	}, [s]);

	const txQ = useQuery({ queryKey: ['adminTx'], queryFn: () => getAdminTransactions({ limit: 100 }) });
	const failedQ = useQuery({
		queryKey: ['adminTxFailed'],
		queryFn: () => getAdminTransactions({ failed_only: true, limit: 50 }),
	});

	const openBillsQ = useQuery({
		queryKey: ['adminOpenPerfBills', cashBillsUserFilter],
		queryFn: () =>
			getAdminOpenPerformanceBills({
				user_id: cashBillsUserFilter,
				limit: 100,
			}),
		enabled: openBillsRequested,
	});

	const recordCashM = useMutation({
		mutationFn: ({ billId, note }: { billId: number; note?: string }) =>
			recordAdminCashPayment(billId, note ? { note } : {}),
		onSuccess: (r) => {
			void qc.invalidateQueries({ queryKey: ['adminOpenPerfBills'] });
			void qc.invalidateQueries({ queryKey: ['adminTx'] });
			setAdminMsg(
				`Cash payment recorded for bill #${r.bill_id} (user ${r.user_id}, ${formatInrPaise(r.amount_paise)}).`
			);
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setAdminMsg(typeof d === 'string' ? d : 'Could not record cash payment');
		},
	});

	const patchM = useMutation({
		mutationFn: patchAdminBillingSettings,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminBillingSettings'] });
			setAdminMsg('Settings saved.');
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setAdminMsg(d ?? 'Save failed');
		},
	});

	const uploadQrM = useMutation({
		mutationFn: uploadAdminOfflinePaymentQr,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminBillingSettings'] });
			setOfflineQrUploaded(true);
			setOfflineQrUrl('');
			setAdminMsg('QR image uploaded.');
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setAdminMsg(typeof d === 'string' ? d : 'QR upload failed');
		},
	});

	const deleteQrM = useMutation({
		mutationFn: deleteAdminOfflinePaymentQr,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminBillingSettings'] });
			setOfflineQrUploaded(false);
			setAdminMsg('Uploaded QR removed.');
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setAdminMsg(typeof d === 'string' ? d : 'Could not remove QR');
		},
	});

	const rzpCredsM = useMutation({
		mutationFn: patchAdminRazorpayCredentials,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminBillingSettings'] });
			setRzKeySecret('');
			setRzWebhookSecret('');
			setRzClearKeyId(false);
			setRzClearKeySecret(false);
			setRzClearWebhook(false);
			setAdminMsg('Razorpay credentials updated.');
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setAdminMsg(typeof d === 'string' ? d : 'Razorpay save failed');
		},
	});

	const reconM = useMutation({
		mutationFn: runBillingReconcile,
		onSuccess: (r) => {
			void qc.invalidateQueries({ queryKey: ['adminTx'] });
			void qc.invalidateQueries({ queryKey: ['adminTxFailed'] });
			void qc.invalidateQueries({ queryKey: ['adminBillingSettings'] });
			setAdminMsg(`Reconcile: ${JSON.stringify(r)}`);
		},
	});

	const refundM = useMutation({
		mutationFn: postAdminRefund,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminTx'] });
			setAdminMsg('Refund submitted.');
			setRefundTxId('');
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setAdminMsg(d ?? 'Refund failed');
		},
	});

	const applyRazorpayCredentials = () => {
		const body: Record<string, unknown> = {};
		if (rzClearKeyId) body.razorpay_key_id = null;
		else if (rzKeyId.trim()) body.razorpay_key_id = rzKeyId.trim();
		if (rzClearKeySecret) body.razorpay_key_secret = null;
		else if (rzKeySecret.length) body.razorpay_key_secret = rzKeySecret;
		if (rzClearWebhook) body.razorpay_webhook_secret = null;
		else if (rzWebhookSecret.length) body.razorpay_webhook_secret = rzWebhookSecret;
		if (!Object.keys(body).length) {
			setAdminMsg('Change a Razorpay field or tick a clear option, then save.');
			return;
		}
		rzpCredsM.mutate(body);
	};

	return (
		<div className="p-4 sm:p-6 max-w-5xl space-y-8 text-[var(--text)]">
			<h1 className="text-xl font-semibold">Admin — Billing</h1>
			{adminMsg ? <p className="text-sm text-amber-300 whitespace-pre-wrap">{adminMsg}</p> : null}

			<section className="p-4 rounded border border-[#1e293b] space-y-3">
				<h2 className="font-medium">Customer payments (beta)</h2>
				<p className="text-xs text-[var(--muted)] leading-relaxed">
					When checkout is off, users pay via UPI/QR. Use{' '}
					<strong className="font-normal text-[var(--text)]">Record cash payment</strong> below after they pay.
				</p>
				{settingsQ.isLoading ? (
					<p className="text-sm text-[var(--muted)]">Loading…</p>
				) : (
					<div className="space-y-4 text-sm">
						<label className="flex items-center gap-2">
							<input
								type="checkbox"
								checked={Boolean((s as Record<string, unknown>)?.online_payments_enabled)}
								onChange={(e) => patchM.mutate({ online_payments_enabled: e.target.checked })}
							/>
							Enable Razorpay checkout on user Billing page
						</label>
						<div className="flex flex-wrap gap-4 text-xs text-[var(--muted)]">
							<label className="flex items-center gap-2">
								<input
									type="checkbox"
									checked={Boolean(s?.payment_card_enabled)}
									onChange={(e) => patchM.mutate({ payment_card_enabled: e.target.checked })}
								/>
								Card (Razorpay, when online enabled)
							</label>
							<label className="flex items-center gap-2">
								<input
									type="checkbox"
									checked={Boolean(s?.payment_upi_enabled)}
									onChange={(e) => patchM.mutate({ payment_upi_enabled: e.target.checked })}
								/>
								UPI in Razorpay modal (when online enabled)
							</label>
						</div>
						<div className="grid gap-3 max-w-lg">
							<label className="flex flex-col gap-1">
								<span className="text-xs text-[var(--muted)]">Offline UPI ID (VPA)</span>
								<input
									className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
									value={offlineUpi}
									onChange={(e) => setOfflineUpi(e.target.value)}
									placeholder="yourname@paytm"
								/>
							</label>
							<label className="flex flex-col gap-1">
								<span className="text-xs text-[var(--muted)]">Payment QR code</span>
								<p className="text-[11px] text-[var(--muted)] leading-relaxed">
									Upload a PNG/JPEG/WebP/GIF (max 2 MB). Shown on user Billing when offline checkout is
									active. Upload replaces any hosted URL below.
								</p>
								<div className="flex flex-wrap items-center gap-2 mt-1">
									<input
										ref={qrFileInputRef}
										type="file"
										accept="image/png,image/jpeg,image/webp,image/gif"
										className="hidden"
										onChange={(e) => {
											const file = e.target.files?.[0];
											e.target.value = '';
											if (file) uploadQrM.mutate(file);
										}}
									/>
									<button
										type="button"
										className="px-3 py-1.5 rounded bg-slate-600 text-white text-sm disabled:opacity-40"
										disabled={uploadQrM.isPending}
										onClick={() => qrFileInputRef.current?.click()}
									>
										{uploadQrM.isPending ? 'Uploading…' : 'Upload QR image'}
									</button>
									{offlineQrUploaded ? (
										<button
											type="button"
											className="px-3 py-1.5 rounded border border-[#1e293b] text-sm text-[var(--muted)] hover:text-[var(--text)]"
											disabled={deleteQrM.isPending}
											onClick={() => deleteQrM.mutate()}
										>
											Remove uploaded QR
										</button>
									) : null}
								</div>
								{offlineQrUploaded ? (
									<div className="mt-2">
										<OfflinePaymentQrPreview key={String(settingsQ.dataUpdatedAt ?? 'qr')} />
									</div>
								) : null}
							</label>
							<label className="flex flex-col gap-1">
								<span className="text-xs text-[var(--muted)]">
									Or hosted QR image URL (optional if you uploaded above)
								</span>
								<input
									className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
									value={offlineQrUrl}
									onChange={(e) => setOfflineQrUrl(e.target.value)}
									placeholder="https://…/paytm-qr.png"
									disabled={offlineQrUploaded}
								/>
							</label>
							<label className="flex flex-col gap-1">
								<span className="text-xs text-[var(--muted)]">Instructions (shown on user Billing)</span>
								<textarea
									className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b] min-h-[4rem]"
									value={offlineInstructions}
									onChange={(e) => setOfflineInstructions(e.target.value)}
									placeholder="Pay exact amount; bill # and email in note."
								/>
							</label>
							<button
								type="button"
								className="px-3 py-1.5 rounded bg-slate-600 text-white w-fit text-sm"
								disabled={patchM.isPending}
								onClick={() =>
									patchM.mutate({
										offline_payment_upi_id: offlineUpi.trim() || null,
										offline_payment_instructions: offlineInstructions.trim() || null,
										offline_payment_qr_image_url: offlineQrUrl.trim() || null,
									})
								}
							>
								Save offline payment details
							</button>
						</div>
					</div>
				)}
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-3 text-sm">
				<h2 className="font-medium">Razorpay credentials</h2>
				<p className="text-xs text-[var(--muted)] leading-relaxed">
					API key secret and webhook secret are encrypted at rest. Use one Fernet key for everything: set{' '}
					<code className="text-[11px]">BROKER_SECRET_KEY</code> or{' '}
					<code className="text-[11px]">APP_DATA_ENCRYPTION_KEY</code> (same value encrypts broker credentials
					and these Razorpay fields—only one env var needed).{' '}
					<code className="text-[11px]">RAZORPAY_KEY_SECRET</code> /{' '}
					<code className="text-[11px]">RAZORPAY_WEBHOOK_SECRET</code> override stored values when set. Saved
					secrets are never shown again.
				</p>
				{settingsQ.isLoading ? (
					<p className="text-sm text-[var(--muted)]">Loading…</p>
				) : (
					<div className="space-y-2 text-xs text-[var(--muted)]">
						<p>
							Key id preview:{' '}
							<span className="text-[var(--text)]">
								{String((s as Record<string, unknown>)?.razorpay_key_id_preview ?? '—')}
							</span>
						</p>
						<p>
							API ready:{' '}
							<span className="text-[var(--text)]">
								{String((s as Record<string, unknown>)?.razorpay_api_configured ?? false)}
							</span>
							{' · '}
							Webhook ready:{' '}
							<span className="text-[var(--text)]">
								{String((s as Record<string, unknown>)?.razorpay_webhook_configured ?? false)}
							</span>
						</p>
						<p>
							Secrets from env: key_secret{' '}
							{String((s as Record<string, unknown>)?.razorpay_key_secret_from_env ?? false)}, webhook{' '}
							{String((s as Record<string, unknown>)?.razorpay_webhook_secret_from_env ?? false)}
						</p>
						<p>
							Stored in DB: key_secret{' '}
							{String((s as Record<string, unknown>)?.razorpay_key_secret_stored_in_db ?? false)}, webhook{' '}
							{String((s as Record<string, unknown>)?.razorpay_webhook_secret_stored_in_db ?? false)}
						</p>
					</div>
				)}
				<div className="flex flex-col gap-2 max-w-md">
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Key ID (optional, stored if env empty)</span>
						<input
							type="text"
							autoComplete="off"
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={rzKeyId}
							onChange={(e) => setRzKeyId(e.target.value)}
							placeholder="rzp_…"
						/>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Key secret (password)</span>
						<PasswordInput
							autoComplete="new-password"
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={rzKeySecret}
							onChange={(e) => setRzKeySecret(e.target.value)}
							placeholder="Leave blank to keep stored value"
						/>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Webhook secret</span>
						<PasswordInput
							autoComplete="new-password"
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={rzWebhookSecret}
							onChange={(e) => setRzWebhookSecret(e.target.value)}
							placeholder="Leave blank to keep stored value"
						/>
					</label>
					<div className="flex flex-col gap-1 text-xs">
						<label className="flex items-center gap-2">
							<input type="checkbox" checked={rzClearKeyId} onChange={(e) => setRzClearKeyId(e.target.checked)} />
							Clear stored Key ID (use env only)
						</label>
						<label className="flex items-center gap-2">
							<input
								type="checkbox"
								checked={rzClearKeySecret}
								onChange={(e) => setRzClearKeySecret(e.target.checked)}
							/>
							Clear stored API secret
						</label>
						<label className="flex items-center gap-2">
							<input type="checkbox" checked={rzClearWebhook} onChange={(e) => setRzClearWebhook(e.target.checked)} />
							Clear stored webhook secret
						</label>
					</div>
					<button
						type="button"
						className="text-sm px-3 py-1.5 rounded bg-indigo-700 text-white w-fit"
						disabled={rzpCredsM.isPending}
						onClick={() => applyRazorpayCredentials()}
					>
						Save Razorpay credentials
					</button>
				</div>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-3 text-sm">
				<h2 className="font-medium">Record cash payment</h2>
				<p className="text-xs text-[var(--muted)] leading-relaxed">
					When a user pays a performance fee offline (cash, bank transfer, etc.), mark their open invoice
					paid here. This clears broker buy blocks and adds a captured transaction (no Razorpay).
				</p>
				<div className="flex flex-wrap gap-2 items-end">
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Filter by user id (optional)</span>
						<input
							className="w-28 px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={cashUserId}
							onChange={(e) => setCashUserId(e.target.value)}
							placeholder="e.g. 2"
						/>
					</label>
					<button
						type="button"
						className="px-3 py-1.5 rounded bg-slate-600 text-white"
						onClick={() => {
							const trimmed = cashUserId.trim();
							setCashBillsUserFilter(trimmed ? Number(trimmed) : undefined);
							setOpenBillsRequested(true);
						}}
					>
						Load open bills
					</button>
					<label className="flex flex-col gap-1 min-w-[12rem]">
						<span className="text-xs text-[var(--muted)]">Memo (optional)</span>
						<input
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={cashNote}
							onChange={(e) => setCashNote(e.target.value)}
							placeholder="Receipt ref, date, etc."
						/>
					</label>
				</div>
				{openBillsQ.isFetching ? (
					<p className="text-xs text-[var(--muted)]">Loading open bills…</p>
				) : !openBillsRequested ? (
					<p className="text-xs text-[var(--muted)]">Click “Load open bills” to list unpaid invoices.</p>
				) : (openBillsQ.data ?? []).length === 0 ? (
					<p className="text-xs text-[var(--muted)]">No open performance bills for this filter.</p>
				) : (
					<div className="max-h-56 overflow-auto text-xs">
						<table className="w-full border-collapse">
							<thead>
								<tr className="text-left text-[var(--muted)]">
									<th className="p-1">Bill</th>
									<th className="p-1">User</th>
									<th className="p-1">Month</th>
									<th className="p-1">Due</th>
									<th className="p-1">Payable</th>
									<th className="p-1">Status</th>
									<th className="p-1" />
								</tr>
							</thead>
							<tbody>
								{(openBillsQ.data ?? []).map((b: AdminPerformanceBill) => (
									<tr key={b.id} className="border-t border-[#1e293b]/60">
										<td className="p-1">{b.id}</td>
										<td className="p-1">
											{b.user_id}
											<span className="text-[var(--muted)] block truncate max-w-[8rem]">
												{b.user_email}
											</span>
										</td>
										<td className="p-1">{String(b.bill_month).slice(0, 7)}</td>
										<td className="p-1">{b.due_at.slice(0, 10)}</td>
										<td className="p-1">₹{b.payable_amount.toFixed(2)}</td>
										<td className="p-1">{b.status.replace(/_/g, ' ')}</td>
										<td className="p-1">
											<button
												type="button"
												className="px-2 py-0.5 rounded bg-emerald-800 text-white disabled:opacity-40"
												disabled={recordCashM.isPending}
												onClick={() => {
													if (
														!window.confirm(
															`Record cash payment of ₹${b.payable_amount.toFixed(2)} for bill #${b.id} (${b.user_email})?`
														)
													) {
														return;
													}
													recordCashM.mutate({
														billId: b.id,
														note: cashNote.trim() || undefined,
													});
												}}
											>
												Mark paid
											</button>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2 text-sm">
				<h2 className="font-medium">Reconciliation</h2>
				<p className="text-xs text-[var(--muted)] leading-relaxed">
					Marks overdue performance-fee bills and refreshes billing-related state. Run periodically or after
					webhook issues.
				</p>
				<button
					type="button"
					className="px-3 py-1.5 rounded bg-slate-600 text-white"
					onClick={() => reconM.mutate()}
					disabled={reconM.isPending}
				>
					Run reconcile
				</button>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2 text-sm">
				<h2 className="font-medium">Refund</h2>
				<div className="flex flex-wrap gap-2 items-end">
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">billing_transaction_id</span>
						<input
							className="w-36 px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={refundTxId}
							onChange={(e) => setRefundTxId(e.target.value)}
						/>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Amount paise (optional)</span>
						<input
							className="w-36 px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={refundAmount}
							onChange={(e) => setRefundAmount(e.target.value)}
						/>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Reason</span>
						<input
							className="min-w-[8rem] px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={refundReason}
							onChange={(e) => setRefundReason(e.target.value)}
						/>
					</label>
					<button
						type="button"
						className="px-3 py-1.5 rounded bg-amber-800 text-white"
						disabled={refundM.isPending || !refundTxId}
						onClick={() =>
							refundM.mutate({
								billing_transaction_id: Number(refundTxId),
								amount_paise: refundAmount ? Number(refundAmount) : null,
								reason: refundReason || null,
							})
						}
					>
						Submit refund
					</button>
				</div>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Failed payments</h2>
				<TxTable rows={failedQ.data ?? []} empty="None" />
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Recent transactions</h2>
				<TxTable rows={txQ.data ?? []} empty="None" />
			</section>
		</div>
	);
}
