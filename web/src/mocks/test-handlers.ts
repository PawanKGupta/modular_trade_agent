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
		return HttpResponse.json({ id: 1, email: 'test@example.com', roles: ['admin'] });
	}),
	// settings
	http.get(API('/user/settings'), async () => {
		return HttpResponse.json({ trade_mode: 'paper', broker: null, broker_status: null });
	}),
	http.put(API('/user/settings'), async ({ request }) => {
		const body = (await request.json()) as any;
		return HttpResponse.json({ trade_mode: body['trade_mode'] ?? 'paper', broker: body['broker'] ?? null, broker_status: null });
	}),
	// admin users
	http.get(API('/admin/users'), async () => {
		return HttpResponse.json([
			{ id: 1, email: 'admin@example.com', name: 'Admin', role: 'admin', is_active: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
			{ id: 2, email: 'user@example.com', name: 'User', role: 'user', is_active: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
		]);
	}),
	http.post(API('/admin/users'), async ({ request }) => {
		const body = (await request.json()) as any;
		return HttpResponse.json({ id: Math.floor(Math.random() * 10000), email: body.email, name: body.name ?? null, role: body.role ?? 'user', is_active: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
	}),
	http.put(API('/admin/users/:id'), async ({ params, request }) => {
		const body = (await request.json()) as any;
		return HttpResponse.json({ id: Number(params.id), email: 'updated@example.com', name: body.name ?? null, role: body.role ?? 'user', is_active: body.is_active ?? true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
	}),
	http.delete(API('/admin/users/:id'), async () => {
		return HttpResponse.json({ ok: true });
	}),
	// signals
	http.get(API('/signals/buying-zone'), async () => {
		return HttpResponse.json([
			{ id: 1, symbol: 'TCS', rsi10: 25.2, ema9: 100, ema200: 90, distance_to_ema9: 5, clean_chart: true, monthly_support_dist: 1.2, confidence: 0.7, ts: new Date().toISOString() },
		]);
	}),
];
