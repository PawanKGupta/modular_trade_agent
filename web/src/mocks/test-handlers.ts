import { http, HttpResponse } from 'msw';

const API = (path: string) => `http://localhost:8000/api/v1${path}`;

export const handlers = [
	// auth
	http.post(API('/auth/login'), async ({ request }) => {
		return HttpResponse.json({ access_token: 'test-token', token_type: 'bearer' });
	}),
	http.post(API('/auth/signup'), async () => {
		return HttpResponse.json({ access_token: 'test-token', token_type: 'bearer' });
	}),
	http.get(API('/auth/me'), async () => {
		return HttpResponse.json({ id: 1, email: 'test@example.com', roles: ['user'] });
	}),
	// settings
	http.get(API('/user/settings'), async () => {
		return HttpResponse.json({ trade_mode: 'paper', broker: null, broker_status: null });
	}),
	http.put(API('/user/settings'), async ({ request }) => {
		const body = (await request.json()) as any;
		return HttpResponse.json({ trade_mode: body['trade_mode'] ?? 'paper', broker: body['broker'] ?? null, broker_status: null });
	}),
	// signals
	http.get(API('/signals/buying-zone'), async () => {
		return HttpResponse.json([
			{ id: 1, symbol: 'TCS', rsi10: 25.2, ema9: 100, ema200: 90, distance_to_ema9: 5, clean_chart: true, monthly_support_dist: 1.2, confidence: 0.7, ts: new Date().toISOString() },
		]);
	}),
];


