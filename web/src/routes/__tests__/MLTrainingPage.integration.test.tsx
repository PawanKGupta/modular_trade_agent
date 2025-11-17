import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient } from '@tanstack/react-query';
import { withProviders } from '@/test/utils';
import { MLTrainingPage } from '../dashboard/MLTrainingPage';

describe('MLTrainingPage (integration)', () => {
	it('renders data provided by API handlers', async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
			},
		});

		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/admin/ml']}>
					<MLTrainingPage />
				</MemoryRouter>,
				{ queryClient }
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/ML Training Management/i)).toBeInTheDocument();
			expect(screen.getByText(/Recent Training Jobs/i)).toBeInTheDocument();
			expect(screen.getByText(/Model Versions/i)).toBeInTheDocument();
			expect(screen.getAllByText(/verdict_classifier/i).length).toBeGreaterThan(0);
		});
	});
});
