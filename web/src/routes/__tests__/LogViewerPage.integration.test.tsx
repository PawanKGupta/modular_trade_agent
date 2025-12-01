import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { LogViewerPage } from '../dashboard/LogViewerPage';

describe('LogViewerPage (integration)', () => {
	it('renders mocked logs from API handlers', async () => {
		const queryClient = new QueryClient({
			defaultOptions: { queries: { retry: false } },
		});

		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/logs']}>
					<LogViewerPage />
				</MemoryRouter>,
				{ queryClient }
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Log Management/i)).toBeInTheDocument();
			expect(screen.getByText(/Analysis task finished successfully/i)).toBeInTheDocument();
			expect(screen.getByText(/Unable to parse symbol/i)).toBeInTheDocument();
		});
	});
});
