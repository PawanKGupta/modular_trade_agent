import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { withProviders } from '@/test/utils';
import { TargetsPage } from '../dashboard/TargetsPage';

describe('TargetsPage', () => {
	it('renders target rows', async () => {
		render(withProviders(<TargetsPage />));
		await screen.findByText(/Tracked Targets/i);
		await screen.findByText('TCS');
		await screen.findByText('INFY');
	});
});
