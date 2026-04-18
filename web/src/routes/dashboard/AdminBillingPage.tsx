import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
	getAdminBillingPlans,
	getAdminBillingSettings,
	getAdminSubscriptions,
	getAdminTransactions,
	getBillingReports,
	patchAdminBillingSettings,
	patchAdminRazorpayCredentials,
	postAdminActivateSubscription,
	postAdminCreatePlan,
	postAdminDeactivatePlan,
	postAdminManualSubscription,
	postAdminRefund,
	postAdminSuspendSubscription,
	runBillingReconcile,
	type AdminPlanCreateInput,
	type BillingPlan,
	type BillingReports,
	type BillingTransaction,
	type UserSubscription,
} from '@/api/billing';

function formatInrPaise(paise: number): string {
	return `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatChurnRate(rate: number | null | undefined): string {
	if (rate == null || Number.isNaN(rate)) return '—';
	return `${(rate * 100).toFixed(2)}%`;
}

function BillingReportsGrid({ data }: { data: BillingReports | undefined }) {
	if (!data) {
		return <p className="text-sm text-[var(--muted)]">No data.</p>;
	}
	const items: { label: string; value: string; hint?: string }[] = [
		{ label: 'Active subscribers', value: String(data.active_subscribers) },
		{
			label: 'Revenue (month)',
			value: formatInrPaise(data.revenue_paise_month),
			hint: 'Recognized in selected period',
		},
		{
			label: 'MRR (approx.)',
			value: formatInrPaise(data.mrr_paise_approx),
			hint: 'Same as month revenue for monthly plans',
		},
		{ label: 'Churned users', value: String(data.churned_users), hint: 'In selected period' },
		{
			label: 'Active at period start',
			value: String(data.active_at_period_start),
			hint: 'Denominator for churn rate',
		},
		{ label: 'Churn rate', value: formatChurnRate(data.churn_rate), hint: 'Churned ÷ active at start' },
	];
	return (
		<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
			{items.map((item) => (
				<div
					key={item.label}
					className="rounded border border-[#1e293b] bg-[#0f1720] p-3 space-y-1"
				>
					<p className="text-xs text-[var(--muted)]">{item.label}</p>
					<p className="text-lg font-semibold tabular-nums">{item.value}</p>
					{item.hint ? <p className="text-[10px] text-[var(--muted)] leading-snug">{item.hint}</p> : null}
				</div>
			))}
		</div>
	);
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
	const [reportsYm, setReportsYm] = useState(() => {
		const d = new Date();
		return { y: d.getFullYear(), m: d.getMonth() + 1 };
	});
	const [adminMsg, setAdminMsg] = useState<string | null>(null);

	const [trialDays, setTrialDays] = useState('');
	const [graceDays, setGraceDays] = useState('');
	const [reminderDays, setReminderDays] = useState('');
	const [dunningHrs, setDunningHrs] = useState('');

	const [rzKeyId, setRzKeyId] = useState('');
	const [rzKeySecret, setRzKeySecret] = useState('');
	const [rzWebhookSecret, setRzWebhookSecret] = useState('');
	const [rzClearKeyId, setRzClearKeyId] = useState(false);
	const [rzClearKeySecret, setRzClearKeySecret] = useState(false);
	const [rzClearWebhook, setRzClearWebhook] = useState(false);

	const [newSlug, setNewSlug] = useState('');
	const [newName, setNewName] = useState('');
	const [newTier, setNewTier] = useState<'paper_basic' | 'auto_advanced'>('paper_basic');
	const [newInterval, setNewInterval] = useState<'month' | 'year'>('month');
	const [newAmount, setNewAmount] = useState('0');
	const [syncRzp, setSyncRzp] = useState(false);

	const [manualUserId, setManualUserId] = useState('');
	const [manualPlanId, setManualPlanId] = useState('');
	const [manualMonths, setManualMonths] = useState('1');

	const [refundTxId, setRefundTxId] = useState('');
	const [refundAmount, setRefundAmount] = useState('');
	const [refundReason, setRefundReason] = useState('');

	const settingsQ = useQuery({ queryKey: ['adminBillingSettings'], queryFn: getAdminBillingSettings });
	const plansQ = useQuery({ queryKey: ['adminBillingPlans'], queryFn: getAdminBillingPlans });
	const subsQ = useQuery({ queryKey: ['adminSubs'], queryFn: () => getAdminSubscriptions(100) });
	const txQ = useQuery({ queryKey: ['adminTx'], queryFn: () => getAdminTransactions({ limit: 100 }) });
	const failedQ = useQuery({
		queryKey: ['adminTxFailed'],
		queryFn: () => getAdminTransactions({ failed_only: true, limit: 50 }),
	});
	const reportsQ = useQuery({
		queryKey: ['billingReports', reportsYm.y, reportsYm.m],
		queryFn: () => getBillingReports(reportsYm.y, reportsYm.m),
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
			void qc.invalidateQueries({ queryKey: ['adminSubs'] });
			setAdminMsg(`Reconcile: ${JSON.stringify(r)}`);
		},
	});

	const createPlanM = useMutation({
		mutationFn: (body: AdminPlanCreateInput) => postAdminCreatePlan(body),
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminBillingPlans'] });
			setAdminMsg('Plan created.');
			setNewSlug('');
			setNewName('');
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setAdminMsg(d ?? 'Create plan failed');
		},
	});

	const deactivatePlanM = useMutation({
		mutationFn: postAdminDeactivatePlan,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminBillingPlans'] });
			setAdminMsg('Plan deactivated.');
		},
	});

	const manualSubM = useMutation({
		mutationFn: postAdminManualSubscription,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminSubs'] });
			setAdminMsg('Manual subscription created.');
		},
		onError: (e: unknown) => {
			const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
			setAdminMsg(d ?? 'Manual subscription failed');
		},
	});

	const activateSubM = useMutation({
		mutationFn: postAdminActivateSubscription,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminSubs'] });
			setAdminMsg('Subscription activated.');
		},
	});

	const suspendSubM = useMutation({
		mutationFn: postAdminSuspendSubscription,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminSubs'] });
			setAdminMsg('Subscription suspended.');
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

	const s = settingsQ.data;

	const applyNumericSettings = () => {
		const body: Record<string, unknown> = {};
		if (trialDays !== '') body.default_trial_days = Number(trialDays);
		if (graceDays !== '') body.grace_period_days = Number(graceDays);
		if (reminderDays !== '') body.renewal_reminder_days_before = Number(reminderDays);
		if (dunningHrs !== '') body.dunning_retry_interval_hours = Number(dunningHrs);
		if (!Object.keys(body).length) {
			setAdminMsg('Enter at least one numeric field to save.');
			return;
		}
		patchM.mutate(body);
	};

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

			<section className="p-4 rounded border border-[#1e293b] space-y-3 text-sm">
				<h2 className="font-medium">Billing timing & trial</h2>
				<p className="text-xs text-[var(--muted)]">
					Current: trial {String(s?.default_trial_days ?? '—')}d · grace {String(s?.grace_period_days ?? '—')}
					d · reminder {String(s?.renewal_reminder_days_before ?? '—')}d before · dunning{' '}
					{String(s?.dunning_retry_interval_hours ?? '—')}h
				</p>
				<div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Default trial days</span>
						<input
							type="number"
							min={0}
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={trialDays}
							onChange={(e) => setTrialDays(e.target.value)}
							placeholder={String(s?.default_trial_days ?? '')}
						/>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Grace period days</span>
						<input
							type="number"
							min={0}
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={graceDays}
							onChange={(e) => setGraceDays(e.target.value)}
							placeholder={String(s?.grace_period_days ?? '')}
						/>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Reminder days before</span>
						<input
							type="number"
							min={1}
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={reminderDays}
							onChange={(e) => setReminderDays(e.target.value)}
							placeholder={String(s?.renewal_reminder_days_before ?? '')}
						/>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Dunning interval (h)</span>
						<input
							type="number"
							min={1}
							className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={dunningHrs}
							onChange={(e) => setDunningHrs(e.target.value)}
							placeholder={String(s?.dunning_retry_interval_hours ?? '')}
						/>
					</label>
				</div>
				<button
					type="button"
					className="text-sm px-3 py-1.5 rounded bg-slate-600 text-white"
					onClick={() => applyNumericSettings()}
					disabled={patchM.isPending}
				>
					Save billing settings
				</button>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<div className="flex flex-wrap items-center justify-between gap-2">
					<h2 className="font-medium">Reports</h2>
					<div className="flex gap-2 items-center text-sm">
						<input
							type="number"
							className="w-20 px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={reportsYm.y}
							onChange={(e) => setReportsYm((x) => ({ ...x, y: Number(e.target.value) }))}
						/>
						<input
							type="number"
							min={1}
							max={12}
							className="w-16 px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={reportsYm.m}
							onChange={(e) => setReportsYm((x) => ({ ...x, m: Number(e.target.value) }))}
						/>
					</div>
				</div>
				{reportsQ.isLoading ? (
					<p className="text-sm text-[var(--muted)]">Loading…</p>
				) : reportsQ.isError ? (
					<p className="text-sm text-red-400">Could not load reports.</p>
				) : (
					<BillingReportsGrid data={reportsQ.data} />
				)}
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-3 text-sm">
				<h2 className="font-medium">Create plan</h2>
				<div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
					<input
						className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
						placeholder="slug"
						value={newSlug}
						onChange={(e) => setNewSlug(e.target.value)}
					/>
					<input
						className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
						placeholder="Display name"
						value={newName}
						onChange={(e) => setNewName(e.target.value)}
					/>
					<select
						className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
						value={newTier}
						onChange={(e) => setNewTier(e.target.value as 'paper_basic' | 'auto_advanced')}
					>
						<option value="paper_basic">paper_basic</option>
						<option value="auto_advanced">auto_advanced</option>
					</select>
					<select
						className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
						value={newInterval}
						onChange={(e) => setNewInterval(e.target.value as 'month' | 'year')}
					>
						<option value="month">month</option>
						<option value="year">year</option>
					</select>
					<input
						type="number"
						min={0}
						className="px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
						placeholder="Amount (paise)"
						value={newAmount}
						onChange={(e) => setNewAmount(e.target.value)}
					/>
					<label className="flex items-center gap-2">
						<input type="checkbox" checked={syncRzp} onChange={(e) => setSyncRzp(e.target.checked)} />
						Sync plan to Razorpay
					</label>
				</div>
				<button
					type="button"
					className="text-sm px-3 py-1.5 rounded bg-blue-600 text-white"
					disabled={createPlanM.isPending || !newSlug.trim() || !newName.trim()}
					onClick={() =>
						createPlanM.mutate({
							slug: newSlug.trim(),
							name: newName.trim(),
							plan_tier: newTier,
							billing_interval: newInterval,
							base_amount_paise: Math.max(0, Number(newAmount) || 0),
							sync_razorpay_plan: syncRzp,
						})
					}
				>
					Create plan
				</button>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-3 text-sm">
				<h2 className="font-medium">Manual subscription</h2>
				<div className="flex flex-wrap gap-2 items-end">
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">User id</span>
						<input
							className="w-28 px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={manualUserId}
							onChange={(e) => setManualUserId(e.target.value)}
						/>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Plan</span>
						<select
							className="min-w-[10rem] px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={manualPlanId}
							onChange={(e) => setManualPlanId(e.target.value)}
						>
							<option value="">—</option>
							{(plansQ.data ?? []).map((p: BillingPlan) => (
								<option key={p.id} value={p.id}>
									{p.slug} (#{p.id})
								</option>
							))}
						</select>
					</label>
					<label className="flex flex-col gap-1">
						<span className="text-xs text-[var(--muted)]">Months</span>
						<input
							type="number"
							min={1}
							className="w-20 px-2 py-1 rounded bg-[#0f1720] border border-[#1e293b]"
							value={manualMonths}
							onChange={(e) => setManualMonths(e.target.value)}
						/>
					</label>
					<button
						type="button"
						className="text-sm px-3 py-1.5 rounded bg-emerald-700 text-white"
						disabled={manualSubM.isPending || !manualUserId || !manualPlanId}
						onClick={() =>
							manualSubM.mutate({
								user_id: Number(manualUserId),
								plan_id: Number(manualPlanId),
								period_months: Math.max(1, Number(manualMonths) || 1),
							})
						}
					>
						Assign
					</button>
				</div>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<div className="flex justify-between items-center">
					<h2 className="font-medium">Subscriptions</h2>
					<button
						type="button"
						className="text-sm px-2 py-1 rounded bg-slate-600 text-white"
						onClick={() => reconM.mutate()}
						disabled={reconM.isPending}
					>
						Run reconcile
					</button>
				</div>
				<div className="max-h-56 overflow-auto text-xs">
					<table className="w-full border-collapse">
						<thead>
							<tr className="text-left text-[var(--muted)]">
								<th className="p-1">ID</th>
								<th className="p-1">User</th>
								<th className="p-1">Plan</th>
								<th className="p-1">Status</th>
								<th className="p-1">Actions</th>
							</tr>
						</thead>
						<tbody>
							{(subsQ.data ?? []).map((r: UserSubscription) => (
								<tr key={r.id} className="border-t border-[#1e293b]/60">
									<td className="p-1">{r.id}</td>
									<td className="p-1">—</td>
									<td className="p-1">{r.plan_id}</td>
									<td className="p-1">{r.status}</td>
									<td className="p-1 flex flex-wrap gap-1">
										<button
											type="button"
											className="px-1.5 py-0.5 rounded bg-emerald-800 text-white"
											disabled={activateSubM.isPending}
											onClick={() => activateSubM.mutate(r.id)}
										>
											Activate
										</button>
										<button
											type="button"
											className="px-1.5 py-0.5 rounded bg-rose-900 text-white"
											disabled={suspendSubM.isPending}
											onClick={() => suspendSubM.mutate(r.id)}
										>
											Suspend
										</button>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Plans (catalog)</h2>
				<ul className="text-sm space-y-2 max-h-48 overflow-auto">
					{(plansQ.data ?? []).map((p: BillingPlan) => (
						<li
							key={p.id}
							className="flex flex-wrap items-center justify-between gap-2 border border-[#1e293b]/60 rounded p-2 bg-[#0f1720]"
						>
							<span>
								{p.slug} — {p.name} ({p.is_active ? 'active' : 'inactive'})
							</span>
							{p.is_active ? (
								<button
									type="button"
									className="text-xs px-2 py-1 rounded bg-rose-900 text-white"
									disabled={deactivatePlanM.isPending}
									onClick={() => deactivatePlanM.mutate(p.id)}
								>
									Deactivate
								</button>
							) : null}
						</li>
					))}
				</ul>
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
