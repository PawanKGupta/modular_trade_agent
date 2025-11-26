import { describe, it, expect } from 'vitest';
import { formatErrorMessage, getErrorSummary } from '../formatError';

describe('formatErrorMessage', () => {
	it('extracts main error before STDERR', () => {
		const error = 'Analysis failed with return code 1 STDERR (tail): Some error message';
		const result = formatErrorMessage(error);
		expect(result).toContain('Analysis failed with return code 1');
	});

	it('extracts error type and message', () => {
		const error = 'Something went wrong ValueError: Invalid input';
		const result = formatErrorMessage(error);
		expect(result).toContain('Error: ValueError: Invalid input');
	});

	it('formats file references in stack trace', () => {
		const error = 'Error File "path/to/file.py", line 10, in main';
		const result = formatErrorMessage(error);
		expect(result).toContain('Stack trace:');
		expect(result).toContain('to/file.py:10 in main()');
	});

	it('shows only last 3 stack trace entries', () => {
		const error = `
			File "file1.py", line 1, in func1
			File "file2.py", line 2, in func2
			File "file3.py", line 3, in func3
			File "file4.py", line 4, in func4
			File "file5.py", line 5, in func5
		`;
		const result = formatErrorMessage(error);
		const lines = result.split('\n');
		// Should have Stack trace: + 3 entries
		const stackLines = lines.filter(line => line.includes('.py:'));
		expect(stackLines.length).toBeLessThanOrEqual(3);
		expect(result).toContain('file3.py:3');
		expect(result).toContain('file4.py:4');
		expect(result).toContain('file5.py:5');
	});

	it('formats the example error message correctly', () => {
		const error = 'Analysis failed with return code 1 STDERR (tail): ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ File "C:\\Personal\\Projects\\TradingView\\modular_trade_agent\\.venv\\Lib\\site-packages\\scipy\\_lib\\_array_api.py", line 677, in __str__ cpu = self._render(self.cpu) ^^^^^^^^^^^^^^^^^^^^^^ File "C:\\Personal\\Projects\\TradingView\\modular_trade_agent\\.venv\\Lib\\site-packages\\scipy\\_lib\\_array_api.py", line 672, in _render AssertionError: Warnings too long';

		const result = formatErrorMessage(error);

		// Should have main error
		expect(result).toContain('Analysis failed with return code 1');

		// Should have error type if present
		if (result.includes('Error:')) {
			expect(result).toContain('AssertionError');
		}

		// Should have concise stack trace
		expect(result).toContain('Stack trace:');
		expect(result).toContain('_array_api.py:677');
		expect(result).toContain('_array_api.py:672');

		// Should NOT have separator lines
		expect(result).not.toContain('^^^^^^^');
	});

	it('handles empty error message', () => {
		expect(formatErrorMessage('')).toBe('');
		expect(formatErrorMessage(null as any)).toBe('');
		expect(formatErrorMessage(undefined as any)).toBe('');
	});

	it('handles simple single-line error', () => {
		const error = 'Connection timeout';
		const result = formatErrorMessage(error);
		expect(result).toBe('Connection timeout');
	});

	it('shortens file paths to last 2 parts', () => {
		const error = 'File "C:\\very\\long\\path\\to\\some\\file.py", line 10';
		const result = formatErrorMessage(error);
		expect(result).toContain('some/file.py:10');
		expect(result).not.toContain('C:\\very\\long\\path');
	});

	it('includes function name in stack trace', () => {
		const error = 'File "test.py", line 10, in my_function';
		const result = formatErrorMessage(error);
		expect(result).toContain('test.py:10 in my_function()');
	});

	it('handles stack trace without function name', () => {
		const error = 'File "test.py", line 10';
		const result = formatErrorMessage(error);
		expect(result).toContain('test.py:10');
		expect(result).not.toContain('in ()');
	});
});

describe('getErrorSummary', () => {
	it('returns first line of error', () => {
		const error = 'First line\nSecond line\nThird line';
		expect(getErrorSummary(error)).toBe('First line');
	});

	it('returns truncated error if no newlines', () => {
		const longError = 'A'.repeat(200);
		const summary = getErrorSummary(longError);
		expect(summary.length).toBeLessThanOrEqual(104); // 100 + '...'
		expect(summary).toContain('...');
	});

	it('handles empty error', () => {
		expect(getErrorSummary('')).toBe('');
		expect(getErrorSummary(null as any)).toBe('');
		expect(getErrorSummary(undefined as any)).toBe('');
	});

	it('handles single line error', () => {
		const error = 'Simple error message';
		expect(getErrorSummary(error)).toBe('Simple error message');
	});
});
