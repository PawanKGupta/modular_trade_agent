import { defineConfig } from 'vitest/config';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
	test: {
		environment: 'jsdom',
		setupFiles: ['./src/test/setup.ts'],
		globals: true,
		coverage: {
			provider: 'v8',
			reporter: ['text', 'html'],
			include: ['src/**/*.ts', 'src/**/*.tsx'],
			exclude: ['src/main.tsx', 'src/router.tsx', 'src/index.css', 'src/mocks/**', 'src/test/**'],
			lines: 80,
			branches: 80,
			functions: 80,
			statements: 80,
		},
	},
	resolve: {
		alias: {
			'@': fileURLToPath(new URL('./src', import.meta.url)),
		},
	},
});
