import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
	getAdminBillingSettings,
	getAdminTransactions,
	patchAdminBillingSettings,
	patchAdminRazorpayCredentials,
	postAdminRefund,
	runBillingReconcile,
	type BillingTransaction,
} from '@/api/billing';

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

	const settingsQ = useQuery({ queryKey: ['adminBillingSettings'], queryFn: getAdminBillingSettings });
	const s = settingsQ.data;
	const txQ = useQuery({ queryKey: ['adminTx'], queryFn: () => getAdminTransactions({ limit: 100 }) });
	const failedQ = useQuery({
		queryKey: ['adminTxFailed'],
		queryFn: () => getAdminTransactions({ failed_only: true, limit: 50 }),
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
				<h2 className="font-medium">Payment toggles</h2>
				{settingsQ.isLoading ? (
					<p className="text-sm text-[var(--muted)]">Loading…</p>
				) : (
					<div className="flex flex-wrap gap-4 text-sm">
						<label className="flex items-center gap-2">
							<input
								type="checkbox"
								checked={Boolean(s?.payment_card_enabled)}
								onChange={(e) => patchM.mutate({ payment_card_enabled: e.target.checked })}
							/>
							Card
						</label>
						<label className="flex items-center gap-2">
							<input
								type="checkbox"
								checked={Boolean(s?.payment_upi_enabled)}
								onChange={(e) => patchM.mutate({ payment_upi_enabled: e.target.checked })}
							/>
							UPI
						</label>
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
						<input
							type="password"
							autoComplete="new-password"
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={rzKeySecret}
							onChange={(e) => setRzKeySecret(e.target.value)}
							placeholder="Leave blank to keep stored value"
						/>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Webhook secret</span>
						<input
							type="password"
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
