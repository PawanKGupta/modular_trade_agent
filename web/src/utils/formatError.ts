/**
 * Format error messages for better readability
 * - Extracts key information
 * - Removes verbose/redundant parts
 * - Presents in a clean, structured format
 */
export function formatErrorMessage(error: string): string {
	if (!error) return '';

	// Extract main error message (before STDERR/STDOUT)
	const mainErrorMatch = error.match(/^(.*?)(?:\s*STDERR|\s*STDOUT|$)/s);
	const mainError = mainErrorMatch ? mainErrorMatch[1].trim() : error;

	// Extract the actual error type and message (e.g., "ValueError: Invalid input")
	const errorTypeMatch = error.match(/([\w]+(?:Error|Exception)):\s*(.+?)(?:\n|$)/);
	const errorType = errorTypeMatch ? `${errorTypeMatch[1]}: ${errorTypeMatch[2]}` : null;

	// Extract file path and line number from stack trace
	const fileMatches = [...error.matchAll(/File "([^"]+)",\s*line\s*(\d+)(?:,\s*in\s+([\w<>]+))?/g)];

	// Build formatted output
	let formatted = '';

	// Add main error
	if (mainError && mainError !== error) {
		formatted += mainError + '\n\n';
	}

	// Add error type if found
	if (errorType) {
		formatted += `Error: ${errorType}\n\n`;
	}

	// Add relevant stack trace info (only last 2-3 entries to keep it concise)
	if (fileMatches.length > 0) {
		formatted += 'Stack trace:\n';
		const relevantMatches = fileMatches.slice(-3); // Last 3 entries
		relevantMatches.forEach((match) => {
			const [, filePath, lineNum, funcName] = match;
			// Shorten file path to show only last 2 parts
			const shortPath = filePath.split(/[/\\]/).slice(-2).join('/');
			formatted += `  • ${shortPath}:${lineNum}`;
			if (funcName) {
				formatted += ` in ${funcName}()`;
			}
			formatted += '\n';
		});
	} else if (!errorType && !mainError.includes('\n')) {
		// If no stack trace and single line, just return the error
		return mainError;
	}

	return formatted.trim();
}

/**
 * Extract error summary (first line) from formatted error
 */
export function getErrorSummary(error: string): string {
	if (!error) return '';
	const lines = error.split('\n');
	const firstLine = lines[0] || error;

	// Truncate if too long
	if (firstLine.length > 100) {
		return firstLine.substring(0, 100) + '...';
	}

	return firstLine;
}
