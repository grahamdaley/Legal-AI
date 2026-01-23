import { test, expect } from "@playwright/test";
import { generateTestUser, createTestUser, deleteTestUser } from "./helpers/test-user";

/**
 * E2E tests for authentication flows.
 * Tests signup, login, and logout against live Supabase.
 */

test.describe("Authentication", () => {
  let testUser: { email: string; password: string };

  test.beforeAll(async () => {
    // Generate unique test user for this test run
    testUser = generateTestUser();
  });

  test.afterAll(async () => {
    // Clean up test user after all tests
    try {
      await deleteTestUser(testUser.email);
    } catch (e) {
      console.log("Cleanup skipped:", e);
    }
  });

  test("should show login and signup buttons when not authenticated", async ({ page }) => {
    await page.goto("/");

    // Should see sign in and sign up buttons in header (use exact match)
    await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Sign up", exact: true })).toBeVisible();
  });

  test("should navigate to signup page", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Sign up", exact: true }).click();

    await expect(page).toHaveURL("/signup");
    // Wait for page to load and check for the card title
    await expect(page.locator("text=Create an account").first()).toBeVisible({ timeout: 10000 });
  });

  test("should show validation error for mismatched passwords", async ({ page }) => {
    await page.goto("/signup");

    await page.getByLabel("Email").fill(testUser.email);
    await page.getByLabel("Password", { exact: true }).fill("password123");
    await page.getByLabel("Confirm Password").fill("differentpassword");
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page.getByText("Passwords do not match")).toBeVisible();
  });

  test("should show validation error for short password", async ({ page }) => {
    await page.goto("/signup");

    await page.getByLabel("Email").fill(testUser.email);
    await page.getByLabel("Password", { exact: true }).fill("12345");
    await page.getByLabel("Confirm Password").fill("12345");
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page.getByText("Password must be at least 6 characters")).toBeVisible();
  });

  test("should create account and redirect to login", async ({ page }) => {
    await page.goto("/signup");

    await page.getByLabel("Email").fill(testUser.email);
    await page.getByLabel("Password", { exact: true }).fill(testUser.password);
    await page.getByLabel("Confirm Password").fill(testUser.password);
    await page.getByRole("button", { name: "Create account" }).click();

    // Should redirect to login with confirmation message (or search if auto-confirmed)
    await expect(page).toHaveURL(/\/(login|search)/, { timeout: 15000 });
  });

  test("should show error for invalid credentials", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel("Email").fill("nonexistent@test.local");
    await page.getByLabel("Password").fill("wrongpassword");
    await page.getByRole("button", { name: "Sign in" }).click();

    // Wait for error message
    await expect(page.getByText(/Invalid login credentials/i)).toBeVisible({ timeout: 10000 });
  });

  test("should login with valid credentials and redirect to search", async ({ page }) => {
    // First create the user via admin API to ensure they exist and are confirmed
    try {
      await createTestUser(testUser);
    } catch (e) {
      // User might already exist from signup test
      console.log("User creation skipped (may already exist):", e);
    }

    await page.goto("/login");

    await page.getByLabel("Email").fill(testUser.email);
    await page.getByLabel("Password").fill(testUser.password);
    await page.getByRole("button", { name: "Sign in" }).click();

    // Should redirect to search page after successful login
    await expect(page).toHaveURL("/search", { timeout: 15000 });

    // Should show user menu instead of login/signup buttons
    await expect(page.getByRole("button", { name: "User menu" })).toBeVisible();
  });

  test("should logout and redirect to home", async ({ page }) => {
    // First login
    try {
      await createTestUser(testUser);
    } catch {
      // User might already exist
    }

    await page.goto("/login");
    await page.getByLabel("Email").fill(testUser.email);
    await page.getByLabel("Password").fill(testUser.password);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL("/search", { timeout: 15000 });

    // Open user menu and click sign out
    await page.getByRole("button", { name: "User menu" }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();

    // Should redirect to home and show login/signup buttons again
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  });
});
