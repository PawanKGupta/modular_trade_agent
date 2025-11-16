import '@testing-library/jest-dom';
import { beforeAll, afterAll, afterEach } from 'vitest';
import { server } from '@/mocks/server';
import { cleanup } from '@testing-library/react';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
	server.resetHandlers();
	cleanup();
});
afterAll(() => server.close());
