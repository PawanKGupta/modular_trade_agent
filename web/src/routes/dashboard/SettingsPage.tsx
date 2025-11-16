import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, type Settings } from '@/api/user';
import { useState, useEffect } from 'react';

export function SettingsPage() {
	const qc = useQueryClient();
	const { data, isLoading } = useQuery<Settings>({ queryKey: ['settings'], queryFn: getSettings });
	const [form, setForm] = useState<Settings>({ trade_mode: 'paper', broker: null, broker_status: null });
	const mutation = useMutation({
		mutationFn: (input: Partial<Settings>) => updateSettings(input),
		onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
	});

	useEffect(() => {
		if (data) setForm(data);
	}, [data]);

	if (isLoading) return <div>Loading settings...</div>;

	const isBroker = form.trade_mode === 'broker';

	return (
		<div className="max-w-xl">
			<h2 className="text-lg font-semibold mb-4">Trading mode</h2>
			<div className="flex items-center gap-4 mb-6">
				<label className="flex items-center gap-2">
					<input type="radio" checked={form.trade_mode === 'paper'} onChange={() => setForm({ ...form, trade_mode: 'paper' })} />
					<span>Paper Trade (default)</span>
				</label>
				<label className="flex items-center gap-2">
					<input type="radio" checked={form.trade_mode === 'broker'} onChange={() => setForm({ ...form, trade_mode: 'broker' })} />
					<span>Kotak Neo</span>
				</label>
			</div>
			{isBroker && (
				<div className="space-y-3 mb-6">
					<div>
						<label className="block text-sm mb-1">Broker</label>
						<input className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]" value={form.broker ?? ''} onChange={(e) => setForm({ ...form, broker: e.target.value })} placeholder="kotak-neo" />
					</div>
					<div className="text-sm text-[var(--muted)]">
						Credentials are managed securely on the server. Use the Connect/Test action in the next phase.
					</div>
				</div>
			)}
			<button
				onClick={() => mutation.mutate({ trade_mode: form.trade_mode, broker: form.broker ?? undefined })}
				className="bg-[var(--accent)] text-black px-4 py-2 rounded"
				disabled={mutation.isPending}
			>
				{mutation.isPending ? 'Saving...' : 'Save settings'}
			</button>
		</div>
	);
}
