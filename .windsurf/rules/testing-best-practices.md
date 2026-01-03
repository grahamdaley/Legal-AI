---
trigger: model_decision
description: This rule should always be applied when developing automated unit, integration or end-to-end (E2E) tests.
---

# Testing Best Practices

Use [Playwright docs](https://playwright.dev/docs) to refer to how to write tests.
Adhere to the [Playwright best practices](https://playwright.dev/docs/best-practices).

## Definition of Done & Test Guidelines

- No Flaky Tests: Ensure reliability through proper async handling, explicit waits, and atomic test design.
- No Hard Waits/Sleeps: Use dynamic waiting strategies (e.g., polling, event-based triggers).
- Stateless & Parallelizable: Tests run independently; use cron jobs or semaphores only if unavoidable.
- No Order Dependency: Every it/describe/context block works in isolation (supports .only execution).
- Self-Cleaning Tests: test sets up its own data and automatically deletes/deactivates entities created during testing.
- Tests Live Near Source Code: Co-locate test files with the code they validate (e.g., \*.spec.js alongside components).
- Shifted Left:

  - Start with local environments or ephemeral stacks.
  - Validate functionality across all deployment stages (local → dev → stage …).

- Low Maintenance: Minimize manual upkeep (e.g., avoid brittle selectors, do not repeat UI actions and leverage APIs).
- Release Confidence:

  - Happy Path: Core user journeys are prioritized.
  - Edge Cases: Critical error/validation scenarios are covered.
  - Feature Flags: Test both enabled and disabled states where applicable.

- CI Execution Evidence: Integrate into pipelines with clear logs/artifacts.
- Visibility: Generate test reports (e.g., JUnit XML, HTML) for failures and trends.
- Test Design:

  - Assertions: Keep them explicit in tests; avoid abstraction into helpers. Use parametrized tests for soft assertions.
  - Naming: Follow conventions (e.g., describe('Component'), it('should do X when Y')).
  - Size: Aim for files ≤200 lines; split/chunk large tests logically.
  - Speed: Target individual tests ≤1.5 mins; optimize slow setups (e.g., shared fixtures).

- Careful Abstractions: Favor readability over DRY when balancing helper reuse (e.g., page objects are okay, assertion logic is not).
- Test Cleanup: Ensure tests clean up resources they create (e.g., closing browser, deleting test data).
- Tests should refrain from using conditionals (e.g., if/else) to control flow or try catch blocks where possible and aim work deterministically.

## API Testing Best Practices

- Tests must not depend on hardcoded data → use **factories** and **per-test setup**.
- Always test both happy path and negative/error cases.
- API tests should run parallel safely (no global state shared).
- Test idempotency where applicable (e.g. duplicate requests).
- Tests should clean up their data.
- Response logs should only be printed in case of failure.
- Auth tests must validate token expiration and renewal.

## E2E Testing Best Practices

Best practices revolve around **stability**, **isolation**, and **maintainability**.

### 1. Robust and User-Focused Locators

* **Prioritize Playwright's Built-in Locators:** Move away from brittle CSS/XPath selectors. Use methods that mimic how a user perceives the page:  
  * page.getByRole() (e.g., button, link, textbox) is the most recommended as it improves accessibility and stability.  
  * page.getByText() for user-facing content.  
  * page.getByLabel(), page.getByPlaceholder(), etc.  
* **Use data-testid Attributes:** For elements that are hard to locate via roles or text, add a stable data-testid attribute (e.g., \<button data-testid="submit-form-button"\>). This separates your test selectors from your UI implementation details.  
* **Be Specific with Strict Locators:** Playwright locators are "strict" by default, meaning they will fail if more than one element matches. This prevents ambiguous interactions.

### 2. Isolation and Setup/Teardown

* **Test Isolation is Critical:** Each test must be completely independent. A failure or side effect in one test should never impact another.  
* **Leverage Fixtures:** Use Playwright's fixture model (test.use(), test.beforeEach(), etc.) to:  
  * Set up a fresh browser context (page, context).  
  * Handle authentication **once** by caching the authenticated state (storageState) and reusing it for tests that require a logged-in user, saving significant time.  
* **Manage Supabase Data:**  
  * For a true E2E test, use a dedicated testing Supabase project or schema.  
  * Use the Supabase API/SDK (in a test.beforeEach() or fixture) to **programmatically create and clean up test data** in your database for each test, ensuring a clean state. **Avoid relying on data left over from a previous test.**

### 3. Asynchronous Operations and Network Control

* **Wait for Network Responses:** Since your app uses external APIs (Supabase), explicitly wait for relevant API calls to complete, especially after an action that triggers a data change (e.g., form submission).  
  * await page.waitForResponse(urlOrPredicate)  
* **Mock External Dependencies:** If a dependency (like a third-party payment gateway or a slow external service) is outside your control and not critical to the E2E flow, use Playwright's **route interception** to mock the response. This stabilizes tests and speeds them up.

### 4. Structure and Maintainability

* **Implement Page Object Model (POM):** Encapsulate all logic and locators for a specific page or major component into a class. This makes tests much easier to read, reuse, and update when the UI changes.  
* **Keep Tests Focused:** Each test should verify a single, specific user workflow (e.g., "User can successfully create a new post," not "User logs in, creates a post, updates a post, and logs out").  
* **Use Trace Viewer:** Enable tracing in your Playwright config (e.g., trace: 'on-first-retry') for easy debugging. The Trace Viewer is a phenomenal tool for diagnosing failures.

### 5. Flaky Tests

Flaky tests are tests that fail non-deterministically (pass sometimes, fail others) without any change to the application code. They are typically caused by **timing issues** or **unstable selectors**.

| Common Flaky Cause | Details & Impact | Playwright Solution |
| :---- | :---- | :---- |
| **Timing/Race Conditions** | Tests try to interact with an element (e.g., click) before the Next.js/React component has fully rendered, an animation finishes, or data is fetched from Supabase. | **Rely on Playwright's Auto-Waiting:** Playwright automatically waits for elements to be "actionable" (visible, enabled, stable). Never use fixed page.waitForTimeout(). |
| **Hardcoded Waits** | Using page.waitForTimeout(3000) to arbitrarily pause execution. This is a band-aid that is too slow when the app is fast, and too short when the app or CI environment is slow. | **Use Web-First Assertions:** Replace hard waits with expect(locator).toBeVisible() or expect(locator).toHaveCount(n) which automatically retry for a set timeout until the condition is met. |
| **Brittle/Dynamic Selectors** | Relying on auto-generated class names, fragile XPath, or nth-child selectors that change frequently during UI refactoring. | **Use Stable Locators:** Switch to page.getByRole(), data-testid, or other reliable, user-facing attributes (as detailed in Best Practices). |
| **Shared State / Data Contamination** | One test modifies a user or database record, and a subsequent test relies on that state, but the first test sometimes fails to clean up properly. | **Enforce Test Isolation:** Use a dedicated test user/context/data-set for *every* test (via beforeEach or fixtures) and ensure a full cleanup/reset using Supabase API calls. |
| **Asynchronous Data** | The test checks for content before the data has returned from your Supabase API call, leading to a failure only when the network/API is slow. | **Wait for Data Conditions:** Use page.waitForResponse() to wait for the API call to complete, or use retrying assertions like await expect(locator).toContainText('Expected data'). |
| **CI/Environment Difference** | Tests pass locally but fail in Netlify's CI/CD pipeline due to resource constraints or slower network speeds. | **Configure Retries:** Set retries: 2 in your playwright.config.ts. This allows transient failures to recover, but you must still investigate the root cause if a test constantly retries before passing. |