import '@testing-library/jest-dom';
import { beforeAll, afterAll, afterEach } from 'vitest';
import { server } from '@/mocks/server';
import { cleanup, configure } from '@testing-library/react';

// Increase default timeout for queries in CI environments
// This helps with slower CI test execution
configure({
	defaultTimeout: 5000, // 5 seconds for findBy queries
});

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
	server.resetHandlers();
	cleanup();
});
afterAll(() => server.close());
