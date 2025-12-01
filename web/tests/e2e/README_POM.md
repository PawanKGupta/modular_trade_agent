# E2E Test Architecture - Page Object Model (POM)

This document describes the Page Object Model (POM) architecture used in the E2E tests for better maintainability and reusability.

## 📁 Directory Structure

```
web/tests/e2e/
├── config/
│   └── test-config.ts          # Centralized configuration
├── pages/
│   ├── BasePage.ts              # Base page class with common methods
│   ├── LoginPage.ts             # Login page object
│   ├── SignupPage.ts            # Signup page object
│   ├── DashboardPage.ts         # Dashboard page object
│   └── index.ts                 # Page objects export
├── fixtures/
│   └── test-fixtures.ts          # Playwright fixtures with page objects
├── utils/
│   └── test-helpers.ts           # Utility functions
├── *.spec.ts                    # Test files
└── README_POM.md                # This file
```

## 🏗️ Architecture Overview

### 1. Configuration (`config/test-config.ts`)

Centralized configuration for all tests:

```typescript
import { TestConfig } from './config/test-config';

// Access configuration
TestConfig.users.admin.email
TestConfig.timeouts.navigation
TestConfig.baseURL
```

**Benefits:**
- No hardcoded values in tests
- Easy to change test data
- Environment variable support
- Single source of truth

### 2. Page Objects (`pages/`)

Each page has its own class with:
- **Selectors**: All element locators
- **Methods**: Actions and interactions
- **Validation**: Page state checks

**Example:**
```typescript
import { LoginPage } from './pages';

const loginPage = new LoginPage(page);
await loginPage.loginAsAdmin();
```

**Benefits:**
- Reusable page interactions
- Centralized selectors (easy to update)
- Clear separation of concerns
- Better test readability

### 3. Base Page (`pages/BasePage.ts`)

Common functionality for all pages:
- `waitForVisible()` - Wait for element visibility
- `clickWithRetry()` - Click with retry logic
- `fillWithRetry()` - Fill input with retry
- `isVisible()` - Check element visibility
- `screenshot()` - Take screenshots

**Benefits:**
- DRY (Don't Repeat Yourself)
- Consistent error handling
- Built-in retry logic

### 4. Test Fixtures (`fixtures/test-fixtures.ts`)

Playwright fixtures that provide:
- `loginPage` - Pre-instantiated LoginPage
- `dashboardPage` - Pre-instantiated DashboardPage
- `signupPage` - Pre-instantiated SignupPage
- `authenticatedPage` - Pre-authenticated page

**Example:**
```typescript
import { test, expect } from './fixtures/test-fixtures';

test('my test', async ({ loginPage, authenticatedPage }) => {
  // loginPage is ready to use
  await loginPage.loginAsAdmin();

  // authenticatedPage is already logged in
  await authenticatedPage.goto('/dashboard');
});
```

**Benefits:**
- Automatic setup/teardown
- Pre-authenticated pages
- Cleaner test code

### 5. Utilities (`utils/test-helpers.ts`)

Helper functions for common operations:
- `loginUser()` - Login helper
- `generateTestEmail()` - Generate unique emails
- `waitForAPIResponse()` - Wait for API calls
- `mockAPIResponse()` - Mock API responses

## 📝 Usage Examples

### Example 1: Using Page Objects

```typescript
import { test, expect } from './fixtures/test-fixtures';

test('login test', async ({ loginPage, page }) => {
  await loginPage.loginAsAdmin();
  await expect(page).toHaveURL(/\/dashboard/);
});
```

### Example 2: Using Pre-authenticated Fixture

```typescript
import { test, expect } from './fixtures/test-fixtures';

test('dashboard test', async ({ authenticatedPage }) => {
  await authenticatedPage.goto('/dashboard');
  // Page is already logged in!
});
```

### Example 3: Using Configuration

```typescript
import { TestConfig } from './config/test-config';

test('test with config', async ({ loginPage }) => {
  await loginPage.login(
    TestConfig.users.admin.email,
    TestConfig.users.admin.password
  );
});
```

### Example 4: Using Utilities

```typescript
import { generateTestEmail, loginUser } from './utils/test-helpers';

test('test with utilities', async ({ page }) => {
  const email = generateTestEmail('testuser');
  await loginUser(page, email, 'password123');
});
```

## 🔧 Creating New Page Objects

1. **Create the page class:**

```typescript
// pages/NewPage.ts
import { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

export class NewPage extends BasePage {
  private readonly someButton: Locator;

  constructor(page: Page) {
    super(page);
    this.someButton = page.getByRole('button', { name: /some button/i });
  }

  async goto(): Promise<void> {
    await this.page.goto('/new-page');
    await this.waitForLoad();
  }

  async clickSomeButton(): Promise<void> {
    await this.clickWithRetry(this.someButton);
  }
}
```

2. **Export it:**

```typescript
// pages/index.ts
export { NewPage } from './NewPage';
```

3. **Add to fixtures (optional):**

```typescript
// fixtures/test-fixtures.ts
newPage: async ({ page }, use) => {
  const newPage = new NewPage(page);
  await use(newPage);
},
```

## 🎯 Best Practices

1. **Use Page Objects**: Always use page objects instead of direct selectors
2. **Use Fixtures**: Leverage fixtures for common setup
3. **Use Configuration**: Never hardcode values
4. **Keep Tests Simple**: Tests should read like user stories
5. **Reuse Methods**: Extract common actions to page objects
6. **Use BasePage**: Extend BasePage for common functionality

## 🔄 Migration Guide

### Before (Old Way):
```typescript
test('login', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/email/i).fill('admin@example.com');
  await page.getByLabel(/password/i).fill('password123');
  await page.getByRole('button', { name: /login/i }).click();
});
```

### After (New Way):
```typescript
test('login', async ({ loginPage }) => {
  await loginPage.loginAsAdmin();
});
```

## 📚 Additional Resources

- [Playwright Page Object Model](https://playwright.dev/docs/pom)
- [Playwright Fixtures](https://playwright.dev/docs/test-fixtures)
- [Test Configuration Guide](./README.md)
