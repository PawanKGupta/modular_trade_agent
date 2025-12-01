import { render, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { RequireAuth } from '../RequireAuth';
import { useSessionStore } from '@/state/sessionStore';

describe('RequireAuth', () => {
	it('redirects when not authenticated after hydration', () => {
		useSessionStore.setState((state) => ({
			...state,
			isAuthenticated: false,
			user: null,
			isAdmin: false,
			hasHydrated: true,
		}));
		const { container } = render(
			<MemoryRouter initialEntries={['/dashboard']}>
				<RequireAuth>
					<div>Protected</div>
				</RequireAuth>
			</MemoryRouter>,
		);
		expect(container.innerHTML).not.toContain('Protected');
	});

	it('initializes session when not hydrated', async () => {
		const initSpy = vi.fn().mockResolvedValue(undefined);
		useSessionStore.setState((state) => ({
			...state,
			isAuthenticated: false,
			user: null,
			isAdmin: false,
			hasHydrated: false,
			initialize: initSpy,
		}));

		render(
			<MemoryRouter initialEntries={['/dashboard']}>
				<RequireAuth>
					<div>Protected</div>
				</RequireAuth>
			</MemoryRouter>,
		);

		await waitFor(() => {
			expect(initSpy).toHaveBeenCalled();
		});
	});
});
