/**
 * Test user management utilities for E2E tests.
 * Uses a dedicated test user that can be created/cleaned up between test runs.
 */

import { createClient } from "@supabase/supabase-js";

// Test user credentials - use environment variables or defaults for local testing
export const TEST_USER = {
  email: process.env.E2E_TEST_EMAIL || `e2e-test-${Date.now()}@test.local`,
  password: process.env.E2E_TEST_PASSWORD || "TestPassword123!",
};

// Generate a unique test user for each test run to avoid conflicts
export function generateTestUser() {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  return {
    email: `e2e-test-${timestamp}-${random}@test.local`,
    password: "TestPassword123!",
  };
}

/**
 * Create a Supabase admin client for test user management.
 * Requires SUPABASE_SERVICE_ROLE_KEY env var for admin operations.
 * Returns null if not available (tests will use UI-based signup instead).
 */
export function getAdminClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "http://127.0.0.1:34321";
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!serviceRoleKey) {
    return null;
  }

  return createClient(supabaseUrl, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}

/**
 * Create a test user directly via Supabase Admin API.
 * This bypasses email confirmation for E2E testing.
 * Returns null if admin client is not available.
 */
export async function createTestUser(user: { email: string; password: string }) {
  const admin = getAdminClient();

  if (!admin) {
    console.log("Admin client not available - user will be created via UI signup");
    return null;
  }

  const { data, error } = await admin.auth.admin.createUser({
    email: user.email,
    password: user.password,
    email_confirm: true, // Auto-confirm for testing
  });

  if (error) {
    throw new Error(`Failed to create test user: ${error.message}`);
  }

  return data.user;
}

/**
 * Delete a test user by email.
 * Silently skips if admin client is not available.
 */
export async function deleteTestUser(email: string) {
  const admin = getAdminClient();

  if (!admin) {
    console.log("Admin client not available - skipping user cleanup");
    return;
  }

  // First find the user by email
  const { data: users, error: listError } = await admin.auth.admin.listUsers();

  if (listError) {
    console.error(`Failed to list users: ${listError.message}`);
    return;
  }

  const user = users.users.find((u) => u.email === email);
  if (!user) {
    console.log(`Test user ${email} not found, skipping deletion`);
    return;
  }

  const { error } = await admin.auth.admin.deleteUser(user.id);

  if (error) {
    console.error(`Failed to delete test user: ${error.message}`);
  }
}

/**
 * Clean up all E2E test users (those matching the e2e-test-* pattern).
 * Silently skips if admin client is not available.
 */
export async function cleanupTestUsers() {
  const admin = getAdminClient();

  if (!admin) {
    console.log("Admin client not available - skipping cleanup");
    return;
  }

  const { data: users, error } = await admin.auth.admin.listUsers();

  if (error) {
    console.error(`Failed to list users for cleanup: ${error.message}`);
    return;
  }

  const testUsers = users.users.filter((u) =>
    u.email?.startsWith("e2e-test-")
  );

  for (const user of testUsers) {
    await admin.auth.admin.deleteUser(user.id);
    console.log(`Cleaned up test user: ${user.email}`);
  }
}
