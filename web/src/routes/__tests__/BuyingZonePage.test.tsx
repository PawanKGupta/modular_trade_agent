import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { BuyingZonePage } from '../dashboard/BuyingZonePage';
import { withProviders } from '@/test/utils';
import * as signalsApi from '@/api/signals';

describe('BuyingZonePage', () => {
	beforeEach(() => {
		// Reset any spies
		vi.clearAllMocks();
	});

	afterEach(async () => {
		// Reset MSW handlers after each test to prevent handler pollution
		const { server } = await import('@/mocks/server');
		server.resetHandlers();
	});

	it('renders signals rows from API', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);
		expect(await screen.findByText(/Buying Zone/i)).toBeInTheDocument();
		expect(await screen.findByText('TCS')).toBeInTheDocument();
		expect(await screen.findByText('INFY')).toBeInTheDocument();
	});

	it('displays default columns', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			// Check table headers (more specific)
			const table = screen.getByRole('table');
			expect(table).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Stock Symbol' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Distance to EMA9' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Backtest' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Confidence' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'ML Confidence' })).toBeInTheDocument();
		});
	});

	it('opens and closes the multi-select dropdown', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
		});

		const dropdownButton = screen.getByRole('button', { name: /column/i });
		expect(dropdownButton).toBeInTheDocument();

		// Open dropdown
		fireEvent.click(dropdownButton);
		await waitFor(() => {
			expect(screen.getByText('RSI10')).toBeInTheDocument();
			expect(screen.getByText('EMA9')).toBeInTheDocument();
		});

		// Close dropdown by clicking outside
		const overlay = document.querySelector('.fixed.inset-0');
		if (overlay) {
			fireEvent.click(overlay);
		}
	});

	it('allows selecting and deselecting columns', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
		});

		const dropdownButton = screen.getByRole('button', { name: /column/i });
		fireEvent.click(dropdownButton);

		await waitFor(() => {
			expect(screen.getByText('RSI10')).toBeInTheDocument();
		});

		// Find and click RSI10 checkbox
		const rsi10Checkbox = screen.getByLabelText(/RSI10/i);
		expect(rsi10Checkbox).not.toBeChecked();
		fireEvent.click(rsi10Checkbox);

		await waitFor(() => {
			expect(rsi10Checkbox).toBeChecked();
		});

		// Deselect it
		fireEvent.click(rsi10Checkbox);
		await waitFor(() => {
			expect(rsi10Checkbox).not.toBeChecked();
		});
	});

	it('enforces minimum column constraint', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
		});

		const dropdownButton = screen.getByRole('button', { name: /column/i });
		fireEvent.click(dropdownButton);

		// Wait for dropdown to open
		await waitFor(() => {
			const allConfidence = screen.getAllByText('Confidence');
			expect(allConfidence.length).toBeGreaterThan(0);
		});

		// Try to deselect a non-mandatory column when at minimum (5 columns)
		// Find the Confidence checkbox in the dropdown (not in table)
		const allCheckboxes = screen.getAllByRole('checkbox');
		const confidenceCheckbox = allCheckboxes.find((cb) => {
			const label = cb.closest('label');
			return label?.textContent?.includes('Confidence') && !label.closest('table');
		});
		expect(confidenceCheckbox).toBeDefined();
		if (confidenceCheckbox) {
			expect(confidenceCheckbox).toBeChecked();
		}

		// At minimum, should be disabled or not allow deselection
		// The checkbox should be enabled but clicking should not deselect if at minimum
		if (confidenceCheckbox) {
			const initialSelectedCount = screen.getByText(/\d+ selected/i).textContent;
			fireEvent.click(confidenceCheckbox);

			// Should still be checked (min constraint prevents deselection)
			await waitFor(() => {
				expect(confidenceCheckbox).toBeChecked();
			});
		}
	});

	it('enforces maximum column constraint', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
		});

		const dropdownButton = screen.getByRole('button', { name: /column/i });
		fireEvent.click(dropdownButton);

		await waitFor(() => {
			expect(screen.getByText('RSI10')).toBeInTheDocument();
		});

		// Select columns until we reach max (10)
		// Start with 5 default, need to add 5 more
		const columnsToAdd = ['RSI10', 'EMA9', 'EMA200', 'Target', 'Stop'];
		for (const colName of columnsToAdd) {
			const allCheckboxes = screen.getAllByRole('checkbox');
			// Find the checkbox in the dropdown (not in the table)
			const checkbox = allCheckboxes.find((cb) => {
				const label = cb.closest('label');
				return label && label.textContent?.includes(colName) && !label.closest('table');
			});
			if (checkbox && !checkbox.checked && !checkbox.disabled) {
				fireEvent.click(checkbox);
				await waitFor(() => {
					expect(checkbox).toBeChecked();
				});
			}
		}

		// Now at max (10), try to select another - should be disabled
		await waitFor(() => {
			const peCheckbox = screen.queryByLabelText(/P\/E/i);
			if (peCheckbox && !peCheckbox.checked) {
				expect(peCheckbox).toBeDisabled();
			}
		});
	});

	it('displays selected columns as chips', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
		});

		// Check that default columns are shown as chips (use getAllByText since "Stock Symbol" appears in both chip and table)
		await waitFor(() => {
			const stockSymbolChips = screen.getAllByText('Stock Symbol');
			expect(stockSymbolChips.length).toBeGreaterThan(0); // At least one (chip or table header)
			expect(screen.getAllByText('Distance to EMA9').length).toBeGreaterThan(0);
			expect(screen.getAllByText('Backtest').length).toBeGreaterThan(0);
		});
	});

	it('prevents deselection of mandatory symbol column', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
		});

		const dropdownButton = screen.getByRole('button', { name: /column/i });
		fireEvent.click(dropdownButton);

		await waitFor(() => {
			const symbolCheckbox = screen.getByLabelText(/Stock Symbol/i);
			expect(symbolCheckbox).toBeChecked();
			expect(symbolCheckbox).toBeDisabled();
		});
	});

	it('displays formatted values correctly', async () => {
		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText('TCS')).toBeInTheDocument();
		});

		// Check that values are formatted correctly
		// Backtest score should be formatted to 2 decimals
		expect(await screen.findByText('75.50')).toBeInTheDocument();
		// ML Confidence should be formatted
		expect(await screen.findByText('0.85')).toBeInTheDocument();
	});

	it('handles empty data gracefully', async () => {
		// Mock empty response
		const { http, HttpResponse } = await import('msw');
		const { server } = await import('@/mocks/server');
		server.use(
			http.get('*/api/v1/signals/buying-zone', () => {
				return HttpResponse.json([]);
			})
		);

		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/No signals found/i)).toBeInTheDocument();
		});
	});

	it('loads saved columns from API', async () => {
		const savedColumns = ['symbol', 'rsi10', 'ema9', 'confidence', 'backtest_score'];
		vi.spyOn(signalsApi, 'getBuyingZoneColumns').mockResolvedValue(savedColumns);

		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(signalsApi.getBuyingZoneColumns).toHaveBeenCalled();
		});

		// Wait for columns to be loaded and applied - check table headers
		await waitFor(() => {
			const table = screen.getByRole('table');
			expect(table).toBeInTheDocument();
			// Check that saved columns appear in table headers
			expect(screen.getByRole('columnheader', { name: 'RSI10' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'EMA9' })).toBeInTheDocument();
		});
	});

	it('saves columns when user changes selection', async () => {
		const saveSpy = vi.spyOn(signalsApi, 'saveBuyingZoneColumns').mockResolvedValue([]);

		render(
			withProviders(
				<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
					<BuyingZonePage />
				</MemoryRouter>
			)
		);

		await waitFor(() => {
			expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
		});

		const dropdownButton = screen.getByRole('button', { name: /column/i });
		fireEvent.click(dropdownButton);

		// Wait for dropdown to open - check for any column name in dropdown (not table)
		await waitFor(() => {
			const allRSI10 = screen.getAllByText('RSI10');
			expect(allRSI10.length).toBeGreaterThan(0);
		});

		// Find RSI10 checkbox in dropdown (not in table)
		const allCheckboxes = screen.getAllByRole('checkbox');
		const rsi10Checkbox = allCheckboxes.find((cb) => {
			const label = cb.closest('label');
			return label?.textContent?.includes('RSI10') && !label.closest('table');
		});

		if (rsi10Checkbox && !rsi10Checkbox.checked && !rsi10Checkbox.disabled) {
			fireEvent.click(rsi10Checkbox);
			await waitFor(() => {
				expect(saveSpy).toHaveBeenCalled();
			});
		} else {
			// If RSI10 is already selected or disabled, try another column like EMA200
			const ema200Checkbox = allCheckboxes.find((cb) => {
				const label = cb.closest('label');
				return label?.textContent?.includes('EMA200') && !label.closest('table');
			});
			if (ema200Checkbox && !ema200Checkbox.checked && !ema200Checkbox.disabled) {
				fireEvent.click(ema200Checkbox);
				await waitFor(() => {
					expect(saveSpy).toHaveBeenCalled();
				});
			}
		}
	});

	describe('Date Grouping', () => {
		it('groups signals by date', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			// Mock signals with different dates
			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'STOCK1',
							ts: '2024-01-15T10:30:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
						{
							symbol: 'STOCK2',
							ts: '2024-01-15T11:00:00',
							distance_to_ema9: 3.2,
							backtest_score: 80.0,
							confidence: 0.90,
							ml_confidence: 0.88,
						},
						{
							symbol: 'STOCK3',
							ts: '2024-01-14T14:00:00',
							distance_to_ema9: 4.1,
							backtest_score: 70.0,
							confidence: 0.75,
							ml_confidence: 0.72,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Should display two date headers (2024-01-15 and 2024-01-14)
			await waitFor(() => {
				expect(screen.getByText(/Jan 15, 2024/i)).toBeInTheDocument();
				expect(screen.getByText(/Jan 14, 2024/i)).toBeInTheDocument();
			});

			// Should display all stocks
			expect(screen.getByText('STOCK1')).toBeInTheDocument();
			expect(screen.getByText('STOCK2')).toBeInTheDocument();
			expect(screen.getByText('STOCK3')).toBeInTheDocument();
		});

		it('displays date header with correct format', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'TEST',
							ts: '2024-03-20T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				// Check for formatted date (e.g., "Wed, Mar 20, 2024")
				expect(screen.getByText(/Mar 20, 2024/i)).toBeInTheDocument();
			});
		});

		it('sorts dates in descending order (newest first)', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'OLD',
							ts: '2024-01-10T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
						{
							symbol: 'NEW',
							ts: '2024-01-20T10:00:00',
							distance_to_ema9: 3.2,
							backtest_score: 80.0,
							confidence: 0.90,
							ml_confidence: 0.88,
						},
						{
							symbol: 'MID',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 4.1,
							backtest_score: 70.0,
							confidence: 0.75,
							ml_confidence: 0.72,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				// Get all h2 elements (date headers)
				const dateHeaders = screen.getAllByRole('heading', { level: 2 });
				// First date should be newest (Jan 20)
				expect(dateHeaders[0].textContent).toContain('Jan 20');
			});
		});

		it('groups multiple signals under same date', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'STOCK1',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
						{
							symbol: 'STOCK2',
							ts: '2024-01-15T11:00:00',
							distance_to_ema9: 3.2,
							backtest_score: 80.0,
							confidence: 0.90,
							ml_confidence: 0.88,
						},
						{
							symbol: 'STOCK3',
							ts: '2024-01-15T14:00:00',
							distance_to_ema9: 4.1,
							backtest_score: 70.0,
							confidence: 0.75,
							ml_confidence: 0.72,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				// Should have only one date header (checking for "Jan 15, 2024")
				expect(screen.getByText(/Jan 15, 2024/i)).toBeInTheDocument();

				// Should have all three stocks under that date
				expect(screen.getByText('STOCK1')).toBeInTheDocument();
				expect(screen.getByText('STOCK2')).toBeInTheDocument();
				expect(screen.getByText('STOCK3')).toBeInTheDocument();
			});
		});

		it('handles signals with invalid timestamps gracefully', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'VALID',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
						{
							symbol: 'INVALID',
							ts: 'invalid-date',
							distance_to_ema9: 3.2,
							backtest_score: 80.0,
							confidence: 0.90,
							ml_confidence: 0.88,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				// Should still display valid signal
				expect(screen.getByText('VALID')).toBeInTheDocument();
				// Should also display invalid signal (under "Invalid Date" or similar)
				expect(screen.getByText('INVALID')).toBeInTheDocument();
			});
		});
	});

	describe('Signal Status', () => {
		it('displays status filter dropdown with all options', async () => {
			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
			});

			// Find status filter dropdown (first combobox)
			const filters = screen.getAllByRole('combobox');
			const statusFilter = filters[0]; // First combobox is status filter
			expect(statusFilter).toBeInTheDocument();

			// Check all options are present
			const options = statusFilter.querySelectorAll('option');
			expect(options).toHaveLength(5);
			expect(options[0].textContent).toContain('Active');
			expect(options[1].textContent).toContain('All');
			expect(options[2].textContent).toContain('Expired');
			expect(options[3].textContent).toContain('Traded');
			expect(options[4].textContent).toContain('Rejected');
		});

		it('defaults to showing only active signals', async () => {
			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
			});

			const filters = screen.getAllByRole('combobox');
			const statusFilter = filters[0]; // First combobox is status filter
			expect(statusFilter).toHaveValue('active');
		});

		it('changes status filter when user selects different option', async () => {
			const getBuyingZoneSpy = vi.spyOn(signalsApi, 'getBuyingZone');

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
			});

			const filters = screen.getAllByRole('combobox');
			const statusFilter = filters[0]; // First combobox is status filter

			// Change to 'all'
			fireEvent.change(statusFilter, { target: { value: 'all' } });

			await waitFor(() => {
				expect(statusFilter).toHaveValue('all');
				expect(getBuyingZoneSpy).toHaveBeenCalledWith(100, null, 'all');
			});
		});

		it('displays status badges with correct colors for active signals', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'ACTIVE1',
							status: 'active',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Wait for page to load and badge to appear
			await waitFor(() => {
				// Get all elements with "✓ Active" text (dropdown option + badge)
				const badges = screen.getAllByText('✓ Active');
				// The badge (span) will be in the table, not in a select option
				const badge = badges.find(el => el.tagName === 'SPAN');
				expect(badge).toBeInTheDocument();
				expect(badge).toHaveClass('text-green-400');
			});
		});

		it('displays status badges with correct colors for expired signals', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'EXPIRED1',
							status: 'expired',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Wait for page to load
			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
			});

			// Need to change filter to see expired signals
			const filters = screen.getAllByRole('combobox');
			const statusFilter = filters[0]; // First combobox is status filter
			fireEvent.change(statusFilter, { target: { value: 'expired' } });

			await waitFor(() => {
				// Get all elements with "⏰ Expired" text (dropdown option + badge)
				const badges = screen.getAllByText('⏰ Expired');
				// The badge (span) will be in the table, not in a select option
				const badge = badges.find(el => el.tagName === 'SPAN');
				expect(badge).toBeInTheDocument();
				expect(badge).toHaveClass('text-gray-400');
			});
		});

		it('displays status badges with correct colors for traded signals', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'TRADED1',
							status: 'traded',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Wait for page to load
			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
			});

			// Need to change filter to see traded signals
			const filters = screen.getAllByRole('combobox');
			const statusFilter = filters[0]; // First combobox is status filter
			fireEvent.change(statusFilter, { target: { value: 'traded' } });

			await waitFor(() => {
				// Get all elements with "✅ Traded" text (dropdown option + badge)
				const badges = screen.getAllByText('✅ Traded');
				// The badge (span) will be in the table, not in a select option
				const badge = badges.find(el => el.tagName === 'SPAN');
				expect(badge).toBeInTheDocument();
				expect(badge).toHaveClass('text-blue-400');
			});
		});

		it('displays status badges with correct colors for rejected signals', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'REJECTED1',
							status: 'rejected',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Wait for page to load
			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
			});

			// Need to change filter to see rejected signals
			const filters = screen.getAllByRole('combobox');
			const statusFilter = filters[0]; // First combobox is status filter
			fireEvent.change(statusFilter, { target: { value: 'rejected' } });

			await waitFor(() => {
				// Get all elements with "❌ Rejected" text (dropdown option + badge)
				const badges = screen.getAllByText('❌ Rejected');
				// The badge (span) will be in the table, not in a select option
				const badge = badges.find(el => el.tagName === 'SPAN');
				expect(badge).toBeInTheDocument();
				expect(badge).toHaveClass('text-red-400');
			});
		});

		it('shows reject button only for active signals', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'ACTIVE1',
							status: 'active',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Wait for page and button to load
			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
				const rejectButton = screen.getByRole('button', { name: /Reject/i });
				expect(rejectButton).toBeInTheDocument();
				expect(rejectButton).not.toBeDisabled();
			});
		});

		it('does not show reject button for expired signals', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'EXPIRED1',
							status: 'expired',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Wait for page to load
			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
			});

			// Change to expired filter
			const filters = screen.getAllByRole('combobox');
			const statusFilter = filters[0]; // First combobox is status filter
			fireEvent.change(statusFilter, { target: { value: 'expired' } });

			await waitFor(() => {
				expect(screen.getByText('EXPIRED1')).toBeInTheDocument();
			});

			// No reject button should be present
			const rejectButton = screen.queryByRole('button', { name: /Reject/i });
			expect(rejectButton).not.toBeInTheDocument();
		});

		it('calls rejectSignal API when reject button is clicked', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			const rejectSpy = vi.spyOn(signalsApi, 'rejectSignal').mockResolvedValue(undefined);

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'ACTIVE1',
							status: 'active',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Wait for data and button to load
			await waitFor(() => {
				expect(screen.getByText('ACTIVE1')).toBeInTheDocument();
				expect(screen.getByRole('button', { name: /Reject/i })).toBeInTheDocument();
			});

			const rejectButton = screen.getByRole('button', { name: /Reject/i });
			fireEvent.click(rejectButton);

			await waitFor(() => {
				expect(rejectSpy).toHaveBeenCalledWith('ACTIVE1');
			});
		});

		it('refetches data after rejecting a signal', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			let callCount = 0;

			server.use(
				http.get('*/api/v1/signals/buying-zone', ({ request }) => {
					const url = new URL(request.url);
					// Only count buying-zone calls, not column settings
					if (url.pathname.includes('buying-zone')) {
						callCount++;
						if (callCount === 1) {
							return HttpResponse.json([
								{
									symbol: 'ACTIVE1',
									status: 'active',
									ts: '2024-01-15T10:00:00',
									distance_to_ema9: 5.5,
									backtest_score: 75.5,
									confidence: 0.85,
									ml_confidence: 0.82,
								},
							]);
						} else {
							// After rejection, signal is removed from active filter
							return HttpResponse.json([]);
						}
					}
					return HttpResponse.json([]);
				}),
				http.patch('*/api/v1/signals/signals/ACTIVE1/reject', () => {
					return HttpResponse.json({ message: 'Signal rejected', symbol: 'ACTIVE1', status: 'rejected' });
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Wait for page to load first
			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
			});

			// Then wait for data and button to load (status column is now default, so reject button should be visible)
			await waitFor(
				() => {
					expect(screen.getByText('ACTIVE1')).toBeInTheDocument();
					expect(screen.getByRole('button', { name: /Reject/i })).toBeInTheDocument();
				},
				{ timeout: 3000 }
			);

			const rejectButton = screen.getByRole('button', { name: /Reject/i });
			fireEvent.click(rejectButton);

			// After rejection, signal should disappear (since we're filtering by active)
			await waitFor(() => {
				expect(screen.queryByText('ACTIVE1')).not.toBeInTheDocument();
				expect(screen.getByText(/No signals found/i)).toBeInTheDocument();
			});
		});

		it('displays mixed statuses correctly when filter is set to "all"', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', () => {
					return HttpResponse.json([
						{
							symbol: 'ACTIVE1',
							status: 'active',
							ts: '2024-01-15T10:00:00',
							distance_to_ema9: 5.5,
							backtest_score: 75.5,
							confidence: 0.85,
							ml_confidence: 0.82,
						},
						{
							symbol: 'EXPIRED1',
							status: 'expired',
							ts: '2024-01-15T09:00:00',
							distance_to_ema9: 3.2,
							backtest_score: 80.0,
							confidence: 0.90,
							ml_confidence: 0.88,
						},
						{
							symbol: 'TRADED1',
							status: 'traded',
							ts: '2024-01-15T08:00:00',
							distance_to_ema9: 4.1,
							backtest_score: 70.0,
							confidence: 0.75,
							ml_confidence: 0.72,
						},
					]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			await waitFor(() => {
				expect(screen.getByText(/Buying Zone/i)).toBeInTheDocument();
			});

			// Change filter to 'all' - use getAllByRole to get both filters, first is status
			const filters = screen.getAllByRole('combobox');
			const statusFilter = filters[0]; // First combobox is status filter
			fireEvent.change(statusFilter, { target: { value: 'all' } });

			await waitFor(() => {
				// All three signals should be visible
				expect(screen.getByText('ACTIVE1')).toBeInTheDocument();
				expect(screen.getByText('EXPIRED1')).toBeInTheDocument();
				expect(screen.getByText('TRADED1')).toBeInTheDocument();

				// All badges should be present (using getAllByText since text appears in dropdown too)
				const activeBadges = screen.getAllByText('✓ Active');
				expect(activeBadges.find(el => el.tagName === 'SPAN')).toBeInTheDocument();

				const expiredBadges = screen.getAllByText('⏰ Expired');
				expect(expiredBadges.find(el => el.tagName === 'SPAN')).toBeInTheDocument();

				const tradedBadges = screen.getAllByText('✅ Traded');
				expect(tradedBadges.find(el => el.tagName === 'SPAN')).toBeInTheDocument();
			});
		});

		it('updates results count to reflect status filter', async () => {
			const { http, HttpResponse } = await import('msw');
			const { server } = await import('@/mocks/server');

			server.use(
				http.get('*/api/v1/signals/buying-zone', ({ request }) => {
					const url = new URL(request.url);
					const statusFilter = url.searchParams.get('status_filter');

					if (statusFilter === 'active') {
						return HttpResponse.json([
							{
								symbol: 'ACTIVE1',
								status: 'active',
								ts: '2024-01-15T10:00:00',
								distance_to_ema9: 5.5,
								backtest_score: 75.5,
								confidence: 0.85,
								ml_confidence: 0.82,
							},
							{
								symbol: 'ACTIVE2',
								status: 'active',
								ts: '2024-01-15T10:00:00',
								distance_to_ema9: 3.2,
								backtest_score: 80.0,
								confidence: 0.90,
								ml_confidence: 0.88,
							},
						]);
					} else if (statusFilter === 'expired') {
						return HttpResponse.json([
							{
								symbol: 'EXPIRED1',
								status: 'expired',
								ts: '2024-01-15T09:00:00',
								distance_to_ema9: 4.1,
								backtest_score: 70.0,
								confidence: 0.75,
								ml_confidence: 0.72,
							},
						]);
					}
					return HttpResponse.json([]);
				})
			);

			render(
				withProviders(
					<MemoryRouter initialEntries={['/dashboard/buying-zone']}>
						<BuyingZonePage />
					</MemoryRouter>
				)
			);

			// Should show 2 active signals
			await waitFor(() => {
				expect(screen.getByText(/Showing 2 active signals/i)).toBeInTheDocument();
			});

			// Change to expired - use getAllByRole to get both filters, first is status
			const filters = screen.getAllByRole('combobox');
			const statusFilter = filters[0]; // First combobox is status filter
			fireEvent.change(statusFilter, { target: { value: 'expired' } });

			// Should show 1 expired signal
			await waitFor(() => {
				expect(screen.getByText(/Showing 1 expired signal/i)).toBeInTheDocument();
			});
		});
	});
});
