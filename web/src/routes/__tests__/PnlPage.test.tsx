import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { PnlPage } from '../dashboard/PnlPage';

describe('PnlPage', () => {
	it('renders summary and daily rows', async () => {
		render(withProviders(<PnlPage />));
		await screen.findByText(/Summary/i);
		await screen.findByText(/Total PnL:/i);
		await screen.findByText('2025-11-10');
	});
});
