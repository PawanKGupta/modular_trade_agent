import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, updateSettings, type Settings, saveBrokerCreds, testBrokerConnection, getBrokerStatus } from '@/api/user';
import { useState, useEffect } from 'react';

export function SettingsPage() {
	const qc = useQueryClient();
	const { data, isLoading } = useQuery<Settings>({ queryKey: ['settings'], queryFn: getSettings });
	const [form, setForm] = useState<Settings>({ trade_mode: 'paper', broker: null, broker_status: null });
	const mutation = useMutation({
		mutationFn: (input: Partial<Settings>) => updateSettings(input),
		onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
	});
	const [apiKey, setApiKey] = useState('');
	const [apiSecret, setApiSecret] = useState('');
	const [brokerMsg, setBrokerMsg] = useState<string | null>(null);
	const [testing, setTesting] = useState(false);
	const [status, setStatus] = useState<{ broker: string | null; status: string | null } | null>(null);

	useEffect(() => {
		getBrokerStatus().then(setStatus).catch(() => {});
	}, []);

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
					<div className="grid grid-cols-1 gap-3">
						<div>
							<label className="block text-sm mb-1">API Key</label>
							<input className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Enter API Key" />
						</div>
						<div>
							<label className="block text-sm mb-1">API Secret</label>
							<input className="w-full p-2 rounded bg-[#0f1720] border border-[#1e293b]" type="password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} placeholder="Enter API Secret" />
						</div>
						<div className="flex gap-2">
							<button
								className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-50"
								onClick={async () => {
									setBrokerMsg(null);
									await saveBrokerCreds(form.broker ?? 'kotak-neo', apiKey, apiSecret);
									setBrokerMsg('Credentials saved');
								}}
								disabled={!apiKey || !apiSecret}
							>
								Save Credentials
							</button>
							<button
								className="bg-emerald-600 text-white px-3 py-2 rounded disabled:opacity-50"
								onClick={async () => {
									setTesting(true);
									const res = await testBrokerConnection(form.broker ?? 'kotak-neo', apiKey, apiSecret);
									setBrokerMsg(res.message ?? (res.ok ? 'OK' : 'Failed'));
									setTesting(false);
									const s = await getBrokerStatus().catch(() => null);
									if (s) setStatus(s);
								}}
								disabled={!apiKey || !apiSecret || testing}
							>
								{testing ? 'Testing...' : 'Test Connection'}
							</button>
						</div>
						{brokerMsg && <div className="text-sm">{brokerMsg}</div>}
						{status && <div className="text-sm text-[var(--muted)]">Status: {status.status ?? 'Unknown'}</div>}
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
