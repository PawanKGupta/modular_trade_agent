import { render } from '@testing-library/react';
import { RequireAuth } from '../RequireAuth';
import { MemoryRouter } from 'react-router-dom';
import { useSessionStore } from '@/state/sessionStore';

describe('RequireAuth', () => {
	it('redirects when not authenticated', () => {
		// ensure store is reset
		useSessionStore.setState({ isAuthenticated: false, user: null, isAdmin: false });
		const { container } = render(
			<MemoryRouter initialEntries={['/dashboard']}>
				<RequireAuth>
					<div>Protected</div>
				</RequireAuth>
			</MemoryRouter>,
		);
		expect(container.innerHTML).not.toContain('Protected');
	});
});
