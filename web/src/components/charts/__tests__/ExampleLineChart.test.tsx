import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ExampleLineChart } from '../ExampleLineChart';

describe('ExampleLineChart', () => {
	it('renders chart with title and data', () => {
		render(
			<ExampleLineChart
				data={[
					{ name: 'Jan', value: 10 },
					{ name: 'Feb', value: 20 },
				]}
				title="Sample trend"
				description="Demo chart"
			/>
		);

		expect(screen.getByText('Sample trend')).toBeInTheDocument();
		expect(screen.getByText('Demo chart')).toBeInTheDocument();
	});
});
