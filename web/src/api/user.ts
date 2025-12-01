import { api } from './client';

export type Settings = {
	trade_mode: 'paper' | 'broker';
	broker?: string | null;
	broker_status?: string | null;
};

export async function getSettings(): Promise<Settings> {
	const res = await api.get('/user/settings');
	return res.data as Settings;
}

export async function updateSettings(input: Partial<Settings>): Promise<Settings> {
	const res = await api.put('/user/settings', input);
	return res.data as Settings;
}

export type BrokerCredsSave = {
	broker: string;
	api_key: string;
	api_secret: string;
	mobile_number?: string;
	password?: string;
	mpin?: string;
	totp_secret?: string;
	environment?: string;
};

export async function saveBrokerCreds(payload: BrokerCredsSave): Promise<{ status: string }> {
	const res = await api.post('/user/broker/creds', payload);
	return res.data as { status: string };
}

export type BrokerTestRequest = {
	broker: string;
	api_key: string;
	api_secret: string;
	mobile_number?: string;
	password?: string;
	mpin?: string;
	totp_secret?: string;
	environment?: string;
};

export async function testBrokerConnection(payload: BrokerTestRequest): Promise<{ ok: boolean; message?: string }> {
	const res = await api.post('/user/broker/test', payload);
	return res.data as { ok: boolean; message?: string };
}

export async function getBrokerStatus(): Promise<{ broker: string | null; status: string | null }> {
	const res = await api.get('/user/broker/status');
	return res.data as { broker: string | null; status: string | null };
}

export type BrokerCredsInfo = {
	has_creds: boolean;
	api_key?: string | null;
	api_secret?: string | null;
	mobile_number?: string | null;
	password?: string | null;
	mpin?: string | null;
	totp_secret?: string | null;
	environment?: string | null;
	api_key_masked?: string | null;
	api_secret_masked?: string | null;
};

export async function getBrokerCredsInfo(showFull = false): Promise<BrokerCredsInfo> {
	const res = await api.get('/user/broker/creds/info', { params: { show_full: showFull } });
	return res.data as BrokerCredsInfo;
}
