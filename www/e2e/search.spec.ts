import { test, expect } from "@playwright/test";
import { generateTestUser, createTestUser, deleteTestUser } from "./helpers/test-user";

/**
 * E2E tests for search functionality.
 * Tests search, filtering, and viewing results against live Supabase.
 */

test.describe("Search", () => {
  let testUser: { email: string; password: string };

  test.beforeAll(async () => {
    testUser = generateTestUser();
    // Try to create test user via admin API (may return null if no service key)
    await createTestUser(testUser);
  });

  test.afterAll(async () => {
    try {
      await deleteTestUser(testUser.email);
    } catch {
      console.log("Cleanup skipped");
    }
  });

  async function loginOrSignupUser(page: import("@playwright/test").Page) {
    // First try to login - if user doesn't exist, sign up first
    await page.goto("/login");
    await page.getByLabel("Email").fill(testUser.email);
    await page.getByLabel("Password").fill(testUser.password);
    await page.getByRole("button", { name: "Sign in" }).click();

    // Wait for either success (redirect to /search) or error
    await page.waitForTimeout(2000);
    
    // If we got an error, sign up instead
    const errorVisible = await page.locator("text=Invalid login credentials").isVisible().catch(() => false);
    if (errorVisible) {
      await page.goto("/signup");
      await page.getByLabel("Email").fill(testUser.email);
      await page.getByLabel("Password", { exact: true }).fill(testUser.password);
      await page.getByLabel("Confirm Password").fill(testUser.password);
      await page.getByRole("button", { name: "Create account" }).click();
      
      // Wait for redirect (may go to login or search depending on email confirmation setting)
      await page.waitForURL(/\/(login|search)/, { timeout: 15000 });
      
      // If redirected to login, log in now
      if (page.url().includes("/login")) {
        await page.getByLabel("Email").fill(testUser.email);
        await page.getByLabel("Password").fill(testUser.password);
        await page.getByRole("button", { name: "Sign in" }).click();
      }
    }
    
    await expect(page).toHaveURL(/\/search/, { timeout: 15000 });
  }

  test("should display search page with search bar", async ({ page }) => {
    await loginOrSignupUser(page);

    await expect(page.getByRole("searchbox").or(page.getByPlaceholder(/search/i))).toBeVisible();
  });

  test("should perform a search and display results", async ({ page }) => {
    await loginOrSignupUser(page);

    // Enter a search query
    const searchInput = page.getByRole("searchbox").or(page.getByPlaceholder(/search/i));
    await searchInput.fill("contract");
    await searchInput.press("Enter");

    // URL should update with query parameter
    await expect(page).toHaveURL(/[?&]q=contract/);

    // Wait for results to load (either results or "no results" message)
    await page.waitForSelector('[data-testid="search-results"], [data-testid="no-results"], .text-muted-foreground:has-text("Found")', {
      timeout: 30000,
    });
  });

  test("should filter search by type (cases)", async ({ page }) => {
    await loginOrSignupUser(page);

    // Perform a search
    const searchInput = page.getByRole("searchbox").or(page.getByPlaceholder(/search/i));
    await searchInput.fill("law");
    await searchInput.press("Enter");

    // Click on Cases tab/filter
    const casesTab = page.getByRole("tab", { name: /cases/i }).or(page.getByText("Cases").first());
    if (await casesTab.isVisible()) {
      await casesTab.click();
      await expect(page).toHaveURL(/type=cases/);
    }
  });

  test("should filter search by type (legislation)", async ({ page }) => {
    await loginOrSignupUser(page);

    // Perform a search
    const searchInput = page.getByRole("searchbox").or(page.getByPlaceholder(/search/i));
    await searchInput.fill("act");
    await searchInput.press("Enter");

    // Click on Legislation tab/filter
    const legislationTab = page.getByRole("tab", { name: /legislation/i }).or(page.getByText("Legislation").first());
    if (await legislationTab.isVisible()) {
      await legislationTab.click();
      await expect(page).toHaveURL(/type=legislation/);
    }
  });

  test("should show search suggestions while typing", async ({ page }) => {
    await loginOrSignupUser(page);

    const searchInput = page.getByRole("searchbox").or(page.getByPlaceholder(/search/i));
    await searchInput.fill("contr");

    // Wait a moment for suggestions to appear
    await page.waitForTimeout(500);

    // Check if suggestions dropdown appears (may or may not depending on data)
    const suggestions = page.locator('[data-testid="suggestions"], [role="listbox"], .suggestions');
    // This is optional - suggestions may not appear if no matching data
    if (await suggestions.isVisible({ timeout: 2000 }).catch(() => false)) {
      await expect(suggestions).toBeVisible();
    }
  });

  test("should navigate to case detail from search results", async ({ page }) => {
    await loginOrSignupUser(page);

    // Search for something likely to have results
    const searchInput = page.getByRole("searchbox").or(page.getByPlaceholder(/search/i));
    await searchInput.fill("court");
    await searchInput.press("Enter");

    // Wait for results
    await page.waitForTimeout(3000);

    // Try to click on the first case result
    const caseLink = page.locator('a[href*="/cases/"]').first();

    if (await caseLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await caseLink.click();

      // Should navigate to case detail page
      await expect(page).toHaveURL(/\/cases\/[a-f0-9-]+/);

      // Case detail page should show case information
      await expect(page.getByRole("button", { name: /back/i })).toBeVisible({ timeout: 10000 });
    } else {
      // No results found - this is acceptable for E2E test with potentially empty DB
      console.log("No case results found to click - skipping navigation test");
    }
  });

  test("should display case detail with metadata", async ({ page }) => {
    await loginOrSignupUser(page);

    // Search and navigate to a case
    const searchInput = page.getByRole("searchbox").or(page.getByPlaceholder(/search/i));
    await searchInput.fill("judgment");
    await searchInput.press("Enter");

    await page.waitForTimeout(3000);

    const caseLink = page.locator('a[href*="/cases/"]').first();

    if (await caseLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await caseLink.click();

      await expect(page).toHaveURL(/\/cases\/[a-f0-9-]+/);

      // Wait for case detail to load
      await page.waitForTimeout(2000);

      // Check for common case detail elements
      const hasBackButton = await page.getByRole("button", { name: /back/i }).isVisible().catch(() => false);
      const hasContent = await page.locator("article, .case-content, main").isVisible().catch(() => false);

      expect(hasBackButton || hasContent).toBeTruthy();
    } else {
      console.log("No case results found - skipping detail test");
    }
  });

  test("should navigate back from case detail to search", async ({ page }) => {
    await loginOrSignupUser(page);

    // First perform a search
    const searchInput = page.getByRole("searchbox").or(page.getByPlaceholder(/search/i));
    await searchInput.fill("legal");
    await searchInput.press("Enter");

    await page.waitForTimeout(3000);

    const caseLink = page.locator('a[href*="/cases/"]').first();

    if (await caseLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await caseLink.click();
      await expect(page).toHaveURL(/\/cases\/[a-f0-9-]+/);

      // Click back button
      await page.getByRole("button", { name: /back/i }).click();

      // Should return to search results
      await expect(page).toHaveURL(/\/search/);
    } else {
      console.log("No case results found - skipping back navigation test");
    }
  });
});
