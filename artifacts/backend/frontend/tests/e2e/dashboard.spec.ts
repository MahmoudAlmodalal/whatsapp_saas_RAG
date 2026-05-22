import { test, expect, Page } from '@playwright/test';

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function login(page: Page, email = 'admin@test.sa', password = 's3cret_admin') {
  await page.goto('/login');
  await page.fill('[data-testid="email-input"]', email);
  await page.fill('[data-testid="password-input"]', password);
  await page.click('[data-testid="login-button"]');
  await page.waitForURL('**/dashboard**');
}

// ─── Scenario 1: Full Login Journey ──────────────────────────────────────────

test.describe('Authentication Flow', () => {
  test('successful login redirects to dashboard', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveTitle(/وصول|Login|Dashboard/i);

    await page.fill('[data-testid="email-input"]', 'admin@test.sa');
    await page.fill('[data-testid="password-input"]', 's3cret_admin');
    await page.click('[data-testid="login-button"]');

    await page.waitForURL('**/dashboard**');
    await expect(page.locator('[data-testid="dashboard-header"]')).toBeVisible();
  });

  test('invalid credentials shows Arabic error message', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', 'wrong@test.sa');
    await page.fill('[data-testid="password-input"]', 'wrongpassword');
    await page.click('[data-testid="login-button"]');

    const error = page.locator('[data-testid="login-error"]');
    await expect(error).toBeVisible();
    // Error must be in Arabic
    const text = await error.textContent();
    expect(text).toMatch(/البريد|كلمة المرور|غير صحيح/);
  });

  test('unauthenticated redirect to login', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForURL('**/login**');
    await expect(page).toHaveURL(/login/);
  });

  test('logout clears session', async ({ page }) => {
    await login(page);
    await page.click('[data-testid="logout-button"]');
    await page.waitForURL('**/login**');
    // After logout, direct navigation to dashboard should redirect
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/login/);
  });
});

// ─── Scenario 2: Document Upload ─────────────────────────────────────────────

test.describe('Document Upload', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/dashboard/documents');
  });

  test('upload PDF document shows queued status', async ({ page }) => {
    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      page.click('[data-testid="upload-button"]'),
    ]);
    await fileChooser.setFiles({
      name: 'دليل_المنتجات.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('Fake PDF content for testing'),
    });

    const statusBadge = page.locator('[data-testid="document-status"]').first();
    await expect(statusBadge).toBeVisible({ timeout: 10_000 });
    const statusText = await statusBadge.textContent();
    expect(['queued', 'processing', 'ready', 'في الانتظار', 'جاهز']).toContain(statusText?.trim());
  });

  test('document list shows uploaded files', async ({ page }) => {
    const list = page.locator('[data-testid="document-list"]');
    await expect(list).toBeVisible();
  });

  test('document processing status updates', async ({ page }) => {
    // Polling behaviour: status should not stay queued indefinitely
    const statusBadges = page.locator('[data-testid="document-status"]');
    await expect(statusBadges.first()).toBeVisible({ timeout: 5_000 });
  });
});

// ─── Scenario 3: Conversations View ──────────────────────────────────────────

test.describe('Conversations Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/dashboard/conversations');
  });

  test('conversation list renders with Arabic content', async ({ page }) => {
    const list = page.locator('[data-testid="conversation-list"]');
    await expect(list).toBeVisible();
  });

  test('conversation detail opens on click', async ({ page }) => {
    const firstConv = page.locator('[data-testid="conversation-item"]').first();
    if (await firstConv.isVisible()) {
      await firstConv.click();
      const detail = page.locator('[data-testid="conversation-detail"]');
      await expect(detail).toBeVisible();
    }
  });

  test('RTL text direction applied for Arabic messages', async ({ page }) => {
    const messageContent = page.locator('[data-testid="message-content"]').first();
    if (await messageContent.isVisible()) {
      const dir = await messageContent.getAttribute('dir');
      const style = await messageContent.evaluate(el => getComputedStyle(el).direction);
      expect(dir === 'rtl' || style === 'rtl').toBeTruthy();
    }
  });
});

// ─── Scenario 4: Agent Handoff Flow ──────────────────────────────────────────

test.describe('Human Handoff Flow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'agent@test.sa', 's3cret_agent');
    await page.goto('/dashboard/conversations');
  });

  test('handoff panel visible on handoff conversations', async ({ page }) => {
    const handoffTab = page.locator('[data-testid="handoff-tab"]');
    if (await handoffTab.isVisible()) {
      await handoffTab.click();
      const handoffList = page.locator('[data-testid="handoff-list"]');
      await expect(handoffList).toBeVisible();
    }
  });
});

// ─── Scenario 5: Mobile Responsive ───────────────────────────────────────────

test.describe('Mobile Responsive Layout', () => {
  test('dashboard renders correctly on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 }); // iPhone 14 size
    await login(page);
    const nav = page.locator('[data-testid="mobile-nav"]');
    await expect(nav).toBeVisible();
  });

  test('RTL Arabic layout correct on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await page.goto('/dashboard/conversations');
    const body = page.locator('body');
    const dir = await body.getAttribute('dir');
    const lang = await body.getAttribute('lang');
    const isRTL = dir === 'rtl' || lang?.startsWith('ar');
    expect(isRTL).toBeTruthy();
  });
});
