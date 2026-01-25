/**
 * Simple in-memory rate limiter for Edge Functions.
 * 
 * Uses a sliding window approach to limit requests per user.
 * Note: This is per-instance and will reset on function cold starts.
 * For production, consider using Redis or Supabase's built-in rate limiting.
 */

interface RateLimitEntry {
  count: number;
  windowStart: number;
}

const rateLimitStore = new Map<string, RateLimitEntry>();

const DEFAULT_WINDOW_MS = 60 * 1000; // 1 minute
const DEFAULT_MAX_REQUESTS = 100; // 100 requests per minute

/**
 * Check if a request should be rate limited.
 * 
 * @param userId - The user ID to check
 * @param maxRequests - Maximum requests allowed in the window
 * @param windowMs - Window duration in milliseconds
 * @returns Object with allowed status and remaining requests
 */
export function checkRateLimit(
  userId: string,
  maxRequests: number = DEFAULT_MAX_REQUESTS,
  windowMs: number = DEFAULT_WINDOW_MS
): { allowed: boolean; remaining: number; resetIn: number } {
  const now = Date.now();
  const entry = rateLimitStore.get(userId);

  // Clean up old entries periodically (every 100 checks)
  if (Math.random() < 0.01) {
    cleanupOldEntries(windowMs);
  }

  if (!entry || now - entry.windowStart >= windowMs) {
    // New window
    rateLimitStore.set(userId, { count: 1, windowStart: now });
    return { allowed: true, remaining: maxRequests - 1, resetIn: windowMs };
  }

  if (entry.count >= maxRequests) {
    // Rate limited
    const resetIn = windowMs - (now - entry.windowStart);
    return { allowed: false, remaining: 0, resetIn };
  }

  // Increment count
  entry.count++;
  const resetIn = windowMs - (now - entry.windowStart);
  return { allowed: true, remaining: maxRequests - entry.count, resetIn };
}

/**
 * Create a rate limit exceeded response.
 */
export function rateLimitResponse(resetIn: number): Response {
  return new Response(
    JSON.stringify({
      error: {
        code: "RATE_LIMITED",
        message: "Too many requests. Please try again later.",
        retryAfter: Math.ceil(resetIn / 1000),
      },
    }),
    {
      status: 429,
      headers: {
        "Content-Type": "application/json",
        "Retry-After": String(Math.ceil(resetIn / 1000)),
      },
    }
  );
}

/**
 * Clean up expired rate limit entries.
 */
function cleanupOldEntries(windowMs: number): void {
  const now = Date.now();
  for (const [key, entry] of rateLimitStore.entries()) {
    if (now - entry.windowStart >= windowMs) {
      rateLimitStore.delete(key);
    }
  }
}
