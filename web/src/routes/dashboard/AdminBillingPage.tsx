import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
	getAdminBillingPlans,
	getAdminBillingSettings,
	getAdminSubscriptions,
	getAdminTransactions,
	getBillingReports,
	patchAdminBillingSettings,
	runBillingReconcile,
	type BillingPlan,
	type UserSubscription,
} from '@/api/billing';

export function AdminBillingPage() {
	const qc = useQueryClient();
	const [reportsYm, setReportsYm] = useState(() => {
		const d = new Date();
		return { y: d.getFullYear(), m: d.getMonth() + 1 };
	});

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
		onSuccess: () => void qc.invalidateQueries({ queryKey: ['adminBillingSettings'] }),
	});

	const reconM = useMutation({
		mutationFn: runBillingReconcile,
		onSuccess: () => {
			void qc.invalidateQueries({ queryKey: ['adminSubs'] });
		},
	});

	const s = settingsQ.data;

	return (
		<div className="p-4 sm:p-6 max-w-5xl space-y-8 text-[var(--text)]">
			<h1 className="text-xl font-semibold">Admin — Billing</h1>

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
				) : (
					<pre className="text-xs overflow-auto bg-[#0f1720] p-3 rounded">
						{JSON.stringify(reportsQ.data, null, 2)}
					</pre>
				)}
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
				<div className="max-h-48 overflow-auto text-xs">
					<table className="w-full border-collapse">
						<thead>
							<tr className="text-left text-[var(--muted)]">
								<th className="p-1">ID</th>
								<th className="p-1">User</th>
								<th className="p-1">Plan</th>
								<th className="p-1">Status</th>
							</tr>
						</thead>
						<tbody>
							{(subsQ.data ?? []).map((r: UserSubscription) => (
								<tr key={r.id} className="border-t border-[#1e293b]/60">
									<td className="p-1">{r.id}</td>
									<td className="p-1">—</td>
									<td className="p-1">{r.plan_id}</td>
									<td className="p-1">{r.status}</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Plans (catalog)</h2>
				<ul className="text-sm space-y-1 max-h-40 overflow-auto">
					{(plansQ.data ?? []).map((p: BillingPlan) => (
						<li key={p.id}>
							{p.slug} — {p.name} ({p.is_active ? 'active' : 'inactive'})
						</li>
					))}
				</ul>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Failed payments</h2>
				<pre className="text-xs overflow-auto bg-[#0f1720] p-3 rounded max-h-40">
					{JSON.stringify(failedQ.data ?? [], null, 2)}
				</pre>
			</section>

			<section className="p-4 rounded border border-[#1e293b] space-y-2">
				<h2 className="font-medium">Recent transactions</h2>
				<pre className="text-xs overflow-auto bg-[#0f1720] p-3 rounded max-h-48">
					{JSON.stringify(txQ.data ?? [], null, 2)}
				</pre>
			</section>
		</div>
	);
}
