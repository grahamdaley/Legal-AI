# Legal-AI Codebase Review Report

**Date:** January 24, 2026  
**Reviewer:** Cascade AI Code Review  
**Scope:** Full codebase review covering code quality, performance, reliability, and security

---

## Executive Summary

The Legal-AI codebase is a well-structured, full-stack application for Hong Kong legal research. It demonstrates good architectural decisions with clear separation between batch processing (Python), edge functions (Deno/TypeScript), frontend (Next.js), and infrastructure (Pulumi). However, there are several areas for improvement across code quality, performance, reliability, and security.

**Overall Assessment:** Good foundation with room for improvement in error handling, code duplication, and security hardening.

---

## 1. Code Quality

### 1.1 Strengths

- **Modular Architecture:** Clear separation between `batch/`, `supabase/functions/`, `www/`, and `infra/` directories
- **Type Safety:** Good use of TypeScript in frontend and Deno functions; Pydantic models in Python
- **Structured Logging:** Consistent use of `structlog` in Python batch jobs
- **Documentation:** Comprehensive README files and inline documentation

### 1.2 Issues & Recommendations

#### 1.2.1 Code Duplication (High Priority)

**Location:** `batch/pipeline/embeddings.py` and `batch/jobs/generate_embeddings_batch.py`

The `_truncate_to_token_limit` function is duplicated:

```python
# In embeddings.py (lines 38-59)
def _truncate_to_token_limit(text: str, max_tokens: int = 4000) -> str:
    ...

# In generate_embeddings_batch.py (lines 51-67)
def _truncate_to_token_limit(text: str, max_tokens: int = 4000) -> str:
    ...
```

**Recommendation:** Extract to a shared utility module `batch/pipeline/utils.py` or `batch/utils/text.py`.

---

#### 1.2.2 Pydantic Model Mixing with Dataclass (Medium Priority)

**Location:** `batch/scrapers/base.py:44-74`

`ScraperState` uses Pydantic's `BaseModel` but defines fields with `field(default_factory=...)` which is a dataclass pattern:

```python
class ScraperState(BaseModel):
    processed_urls: set[str] = field(default_factory=set)  # Wrong!
```

**Recommendation:** Use Pydantic's `Field(default_factory=...)` instead:

```python
from pydantic import Field

class ScraperState(BaseModel):
    processed_urls: set[str] = Field(default_factory=set)
```

---

#### 1.2.3 Deprecated `datetime.utcnow()` Usage (Low Priority)

**Location:** `batch/scrapers/base.py:81`

```python
scraped_at: datetime = field(default_factory=datetime.utcnow)
```

**Recommendation:** Use timezone-aware datetime:

```python
from datetime import datetime, timezone
scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

---

#### 1.2.4 Long Files Exceeding 250 Lines (Medium Priority)

Several files exceed the recommended 250-line limit from project rules:

| File | Lines |
| ------ | ------- |
| `batch/jobs/generate_embeddings_batch.py` | 668 |
| `batch/scrapers/judiciary/scraper.py` | 514 |
| `batch/scrapers/judiciary/parsers.py` | 473 |
| `batch/jobs/ingest_jsonl.py` | 470 |
| `batch/pipeline/embeddings.py` | 416 |

**Recommendation:** Refactor into smaller, focused modules. For example, split `generate_embeddings_batch.py` into:

- `batch/jobs/embeddings/export.py`
- `batch/jobs/embeddings/submit.py`
- `batch/jobs/embeddings/ingest.py`
- `batch/jobs/embeddings/cli.py`

---

#### 1.2.5 Inconsistent Error Response Handling (Low Priority)

**Location:** `www/src/lib/api/search.ts`

Error handling assumes JSON response but doesn't handle non-JSON errors:

```typescript
if (!response.ok) {
  const error = await response.json();  // May throw if not JSON
  throw new Error(error.error?.message || "Search failed");
}
```

**Recommendation:** Add try-catch for JSON parsing:

```typescript
if (!response.ok) {
  try {
    const error = await response.json();
    throw new Error(error.error?.message || "Search failed");
  } catch {
    throw new Error(`Search failed with status ${response.status}`);
  }
}
```

---

## 2. Performance

### 2.1 Strengths

- **Batch Processing:** Good use of AWS Bedrock batch API for embeddings
- **Async Operations:** Proper use of `asyncio` in Python scrapers
- **Database Indexes:** Comprehensive indexing strategy in migrations
- **Lifecycle Policies:** S3/Azure blob lifecycle policies for cleanup

### 2.2 Issues & Recommendations

#### 2.2.1 Sequential Database Inserts (High Priority)

**Location:** `batch/pipeline/embeddings.py:362-364` and `batch/pipeline/embeddings.py:403-405`

Embeddings are inserted one row at a time within a transaction:

```python
async with conn.transaction():
    for row in rows:
        await conn.execute(sql, *row)
```

**Recommendation:** Use `executemany` or batch inserts:

```python
async with conn.transaction():
    await conn.executemany(sql, rows)
```

This can provide 10-100x speedup for large batches.

---

#### 2.2.2 Inefficient List Index Lookup (Medium Priority)

**Location:** `batch/jobs/generate_embeddings_batch.py:180-181`

```python
if (rows.index(row) + 1) % 100 == 0:
    log.info("Progress", processed_cases=rows.index(row) + 1, ...)
```

`rows.index(row)` is O(n), called twice per iteration.

**Recommendation:** Use `enumerate`:

```python
for idx, row in enumerate(rows):
    ...
    if (idx + 1) % 100 == 0:
        log.info("Progress", processed_cases=idx + 1, ...)
```

---

#### 2.2.3 Missing Connection Pooling (Medium Priority)

**Location:** `batch/pipeline/summarizer.py:63-65`

Each call to `generate_headnote` creates a new database connection:

```python
conn = await _get_db_connection()
try:
    ...
finally:
    await conn.close()
```

**Recommendation:** Use a connection pool for batch operations:

```python
from asyncpg import create_pool

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await create_pool(settings.supabase_db_url, min_size=2, max_size=10)
    return _pool
```

---

#### 2.2.4 Embedding Generation Not Parallelized (Medium Priority)

**Location:** `batch/pipeline/embeddings.py:136`

Embeddings are generated sequentially:

```python
return [await _one(t) for t in texts]
```

**Recommendation:** Use `asyncio.gather` for parallel execution:

```python
return await asyncio.gather(*[_one(t) for t in texts])
```

---

#### 2.2.5 Frontend: Missing React Query Caching (Low Priority)

**Location:** `www/src/lib/api/search.ts`

API calls don't leverage React Query's caching capabilities.

**Recommendation:** Wrap API calls in React Query hooks with appropriate `staleTime` and `cacheTime` settings.

---

## 3. Reliability

### 3.1 Strengths

- **Retry Logic:** Good use of `tenacity` for exponential backoff in scrapers
- **State Persistence:** Scraper state saved periodically for resume capability
- **Error Boundaries:** React ErrorBoundary implemented in frontend
- **Structured Error Responses:** Consistent error format in Supabase functions

### 3.2 Issues & Recommendations

#### 3.2.1 Silent Exception Swallowing (High Priority)

**Location:** `batch/scrapers/base.py:163-165`

```python
except Exception as e:
    self._log.warning("Failed to load state, starting fresh", error=str(e))
    self._state = ScraperState(scraper_name=self.name)
```

State corruption is silently ignored.

**Recommendation:** Add more specific exception handling and consider backing up corrupted state:

```python
except json.JSONDecodeError as e:
    self._log.error("Corrupted state file, backing up and starting fresh", error=str(e))
    state_path.rename(state_path.with_suffix('.json.bak'))
    self._state = ScraperState(scraper_name=self.name)
except Exception as e:
    self._log.error("Unexpected error loading state", error=str(e), exc_info=True)
    raise
```

---

#### 3.2.2 Missing Timeout on External API Calls (High Priority)

**Location:** `supabase/functions/_shared/bedrock.ts:115-123`

No timeout configured for Bedrock API calls:

```typescript
const response = await fetch(endpoint, {
  method,
  headers: {...},
  body,
});
```

**Recommendation:** Add AbortController with timeout:

```typescript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 30000);

try {
  const response = await fetch(endpoint, {
    method,
    headers: {...},
    body,
    signal: controller.signal,
  });
  ...
} finally {
  clearTimeout(timeoutId);
}
```

---

#### 3.2.3 Duplicate Migration Files (Medium Priority)

**Location:** `supabase/migrations/`

Two migration files with nearly identical names and content:
- `20260121163800_fix_legislation_ambiguous_column.sql`
- `20260121163900_fix_legislation_ambiguous_column.sql`

**Recommendation:** Review and remove duplicate migration if safe. Consider using `supabase migration new` consistently.

---

#### 3.2.4 No Circuit Breaker for External Services (Medium Priority)

**Location:** Multiple files calling AWS Bedrock, Azure OpenAI

External API calls lack circuit breaker patterns to prevent cascade failures.

**Recommendation:** Implement circuit breaker using `tenacity` or a dedicated library:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, CircuitBreaker

circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

@retry(stop=stop_after_attempt(3), wait=wait_exponential())
@circuit_breaker
async def call_external_api():
    ...
```

---

#### 3.2.5 Graceful Shutdown Not Implemented (Low Priority)

**Location:** `batch/jobs/generate_embeddings_batch.py`

Long-running batch jobs don't handle SIGINT/SIGTERM for graceful shutdown.

**Recommendation:** Add signal handlers:

```python
import signal

shutdown_requested = False

def handle_shutdown(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    log.info("Shutdown requested, finishing current batch...")

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)
```

---

## 4. Security

### 4.1 Strengths

- **RLS Enabled:** Row Level Security enabled on all database tables
- **Service Role Separation:** Write operations restricted to service role
- **HTTPS Enforcement:** Azure storage requires HTTPS
- **Public Access Blocked:** S3 buckets have public access blocked
- **JWT Verification:** Auth tokens verified in Supabase functions

### 4.2 Issues & Recommendations

#### 4.2.1 JWT Verification Bypass in Development (Critical)

**Location:** `supabase/functions/_shared/db.ts:54-74`

JWT is decoded without cryptographic verification:

```typescript
// For local development, decode the JWT without verification
// In production, the Edge Runtime verifies JWTs automatically
try {
  const parts = token.split(".");
  const payload = JSON.parse(atob(parts[1]...));
  return payload.sub || null;
}
```

**Risk:** If this code runs in production, any crafted JWT would be accepted.

**Recommendation:** Use Supabase's built-in JWT verification:

```typescript
import { createClient } from "@supabase/supabase-js";

export async function verifyAuthHeader(authHeader: string): Promise<string | null> {
  const supabase = getSupabaseClient();
  const { data: { user }, error } = await supabase.auth.getUser(
    authHeader.replace("Bearer ", "")
  );
  return error ? null : user?.id ?? null;
}
```

---

#### 4.2.2 SQL Injection Risk via Table Name (High Priority)

**Location:** `batch/pipeline/embeddings.py:351-360`

Table name is interpolated directly into SQL:

```python
sql = f"""
INSERT INTO {table} (case_id, chunk_index, ...)
...
"""
```

While `table` is currently hardcoded, this pattern is dangerous.

**Recommendation:** Use an allowlist:

```python
ALLOWED_TABLES = {"case_embeddings_cohere", "case_embeddings_openai"}

async def _insert_case_embeddings(conn, *, table: str, embeddings):
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table: {table}")
    ...
```

---

#### 4.2.3 Secrets in Pulumi Exports (Medium Priority)

**Location:** `infra/aws/index.ts:236` and `infra/azure/index.ts:277`

Secrets are exported (though marked as `pulumi.secret`):

```typescript
export const appUserSecretAccessKey = pulumi.secret(appUserAccessKey.secret);
export const servicePrincipalClientSecret = pulumi.secret(spPassword.value);
```

**Recommendation:** Avoid exporting secrets. Instead, write them directly to a secrets manager:

```typescript
// Store in AWS Secrets Manager instead of exporting
new aws.secretsmanager.Secret("app-credentials", {
  secretString: pulumi.secret(JSON.stringify({
    accessKeyId: appUserAccessKey.id,
    secretAccessKey: appUserAccessKey.secret,
  })),
});
```

---

#### 4.2.4 Missing Rate Limiting on API Endpoints (Medium Priority)

**Location:** `supabase/functions/search/index.ts`

No rate limiting implemented on search endpoint.

**Recommendation:** Implement rate limiting using Supabase's built-in features or a custom solution:

```typescript
const RATE_LIMIT = 100; // requests per minute per user
const rateLimitKey = `rate_limit:${userId}`;

// Check rate limit before processing
const count = await redis.incr(rateLimitKey);
if (count === 1) {
  await redis.expire(rateLimitKey, 60);
}
if (count > RATE_LIMIT) {
  return new Response(JSON.stringify({ error: "Rate limit exceeded" }), { status: 429 });
}
```

---

#### 4.2.5 Cookie Security Configuration (Low Priority)

**Location:** `www/src/lib/supabase/client.ts:26-32`

Cookie security depends on protocol detection:

```typescript
const isHttps = typeof location !== 'undefined' && location.protocol === 'https:';
const secure = isHttps ? '; Secure' : '';
```

**Recommendation:** Also set `HttpOnly` where possible and ensure `SameSite=Strict` for sensitive cookies.

---

#### 4.2.6 Robots.txt Compliance Warning (Low Priority)

**Location:** `batch/scrapers/judiciary/scraper.py:6-8`

The scraper acknowledges robots.txt restrictions but proceeds anyway:

```python
# IMPORTANT: The Judiciary website's robots.txt disallows automated access.
# This scraper should only be used with proper authorization or for testing.
```

**Recommendation:** Implement robots.txt checking or document authorization clearly.

---

## 5. Testing

### 5.1 Current State

- **Python Tests:** Good coverage in `batch/tests/` with unit tests for parsers, chunking, embeddings
- **Frontend Tests:** Basic setup in `www/src/__tests__/` but limited coverage
- **E2E Tests:** Playwright tests exist in `www/e2e/`

### 5.2 Recommendations

#### 5.2.1 Add Integration Tests for Database Operations

**Location:** `batch/tests/`

Current tests mock database connections. Add integration tests with a test database.

#### 5.2.2 Add API Contract Tests

**Location:** `supabase/functions/tests/`

Tests exist but should include contract testing to ensure API responses match TypeScript types.

#### 5.2.3 Add Load Testing

Consider adding k6 or Artillery load tests for the search endpoint to validate performance under load.

---

## 6. Summary of Priorities

### Critical (Fix Immediately)

1. JWT verification bypass in development mode
2. SQL injection risk via table name interpolation

### High Priority

1. Code duplication in truncation functions
2. Sequential database inserts (performance)
3. Silent exception swallowing in state loading
4. Missing timeout on external API calls

### Medium Priority

1. Pydantic/dataclass mixing
2. Long files exceeding 250 lines
3. Inefficient list index lookup
4. Missing connection pooling
5. Duplicate migration files
6. No circuit breaker pattern
7. Secrets in Pulumi exports
8. Missing rate limiting

### Low Priority

1. Deprecated `datetime.utcnow()` usage
2. Inconsistent error response handling
3. Frontend React Query caching
4. Graceful shutdown handling
5. Cookie security configuration
6. Robots.txt compliance

---

## 7. Recommended Next Steps

1. **Immediate:** Address critical security issues (JWT verification, SQL injection)
2. **Short-term:** Refactor duplicated code and fix high-priority performance issues
3. **Medium-term:** Implement circuit breakers, rate limiting, and connection pooling
4. **Long-term:** Improve test coverage and add load testing

---

*This report was generated by automated code review. Manual verification is recommended for all findings.*
