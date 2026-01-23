# Testing Guide

This document describes the testing strategy and how to run tests across all layers of the Legal-AI application.

## Overview

The application has three test layers:

| Layer | Framework | Location | Description |
|-------|-----------|----------|-------------|
| UI | Vitest + React Testing Library | `www/src/__tests__/` | React component and API client tests |
| Edge Functions | Deno Test | `supabase/functions/tests/` | Supabase Edge Function tests |
| Batch Processing | pytest | `batch/tests/` | Python pipeline and job tests |

## 1. UI Tests (Vitest)

### Setup

```bash
cd www
npm install
```

### Running Tests

```bash
# Run tests in watch mode
npm test

# Run tests once
npm run test:run

# Run tests with coverage
npm run test:coverage
```

### Test Structure

```
www/src/__tests__/
├── setup.ts                    # Test setup and mocks
├── components/
│   ├── cases/
│   │   └── case-header.test.tsx
│   ├── search/
│   │   └── search-bar.test.tsx
│   └── ui/
│       └── button.test.tsx
└── lib/
    └── api/
        └── search.test.ts
```

### Key Test Files

- **`search-bar.test.tsx`** - Tests for the main search component including:
  - Input handling and validation
  - Suggestion fetching and display
  - Keyboard navigation
  - Form submission

- **`case-header.test.tsx`** - Tests for case detail header including:
  - Rendering case metadata
  - Share functionality
  - PDF download link

- **`button.test.tsx`** - Tests for the Button UI component variants

- **`search.test.ts`** - Tests for the search API client including:
  - Request/response handling
  - Authentication headers
  - Error handling

## 2. Supabase Edge Function Tests (Deno)

### Setup

Ensure you have Deno installed and Supabase CLI configured.

### Running Tests

```bash
# Start local Supabase
supabase start

# Run all edge function tests
deno test --allow-net --allow-env supabase/functions/tests/

# Run specific test file
deno test --allow-net --allow-env supabase/functions/tests/search_test.ts
```

### Test Structure

```
supabase/functions/tests/
├── test_utils.ts       # Shared test utilities
├── cases_test.ts       # Cases endpoint tests
├── collections_test.ts # Collections endpoint tests
├── legislation_test.ts # Legislation endpoint tests
├── search_test.ts      # Search endpoint tests
├── shared_test.ts      # Shared utilities tests (CORS, errors)
├── suggestions_test.ts # Suggestions endpoint tests
└── users_test.ts       # Users endpoint tests
```

### Key Test Files

- **`shared_test.ts`** - Tests for shared utilities:
  - CORS header configuration
  - Error response formatting
  - HTTP status codes

- **`search_test.ts`** - Tests for the search endpoint:
  - Request validation
  - Search modes (semantic, hybrid)
  - Filter handling

## 3. Batch Processing Tests (pytest)

### Setup

```bash
cd batch
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_chunking.py

# Run specific test class
pytest tests/test_chunking.py::TestChunkCaseText

# Run with coverage
pytest --cov=pipeline --cov-report=html
```

### Test Structure

```
batch/tests/
├── __init__.py
├── test_chunking.py      # Text chunking tests
├── test_embeddings.py    # Embedding generation tests
├── test_summarizer.py    # Headnote generation tests
├── test_citation_parser.py # Citation parsing tests
├── test_rate_limiter.py  # Rate limiting tests
└── test_scrapers.py      # Web scraper tests
```

### Key Test Files

- **`test_chunking.py`** - Tests for text chunking:
  - Paragraph splitting
  - Chunk grouping with overlap
  - Case and legislation chunking

- **`test_embeddings.py`** - Tests for embedding generation:
  - Token estimation
  - Text truncation
  - Bedrock backend mocking

- **`test_summarizer.py`** - Tests for headnote generation:
  - Prompt building
  - Few-shot retrieval
  - Model routing (Azure/Bedrock)

## Writing New Tests

### UI Tests (Vitest)

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MyComponent } from '@/components/my-component';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Expected text')).toBeInTheDocument();
  });

  it('handles user interaction', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<MyComponent onClick={onClick} />);
    
    await user.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalled();
  });
});
```

### Edge Function Tests (Deno)

```typescript
import { assertEquals } from "https://deno.land/std@0.168.0/testing/asserts.ts";
import { fetchFunction } from "./test_utils.ts";

Deno.test("MyFunction - handles valid request", async () => {
  const response = await fetchFunction("my-function", {
    method: "POST",
    body: { data: "test" },
  });
  
  assertEquals(response.status, 200);
  const body = await response.json();
  assertEquals(body.success, true);
});
```

### Batch Tests (pytest)

```python
import pytest
from unittest.mock import AsyncMock, patch

class TestMyModule:
    def test_sync_function(self):
        result = my_function("input")
        assert result == "expected"

    @pytest.mark.asyncio
    async def test_async_function(self):
        with patch("module.dependency") as mock_dep:
            mock_dep.return_value = AsyncMock(return_value="mocked")
            result = await my_async_function()
            assert result == "expected"
```

## CI/CD Integration

Tests can be run in CI pipelines:

```yaml
# Example GitHub Actions workflow
jobs:
  test-ui:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: cd www && npm ci && npm run test:run

  test-edge-functions:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: denoland/setup-deno@v1
      - uses: supabase/setup-cli@v1
      - run: supabase start
      - run: deno test --allow-net --allow-env supabase/functions/tests/

  test-batch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: cd batch && pip install -r requirements.txt && pytest
```

## Coverage Goals

| Layer | Target Coverage |
|-------|-----------------|
| UI Components | 80% |
| API Clients | 90% |
| Edge Functions | 85% |
| Batch Pipeline | 85% |

## Troubleshooting

### UI Tests

- **Module not found errors**: Run `npm install` to install dependencies
- **Mock issues**: Check `setup.ts` for proper mock configuration

### Edge Function Tests

- **Connection refused**: Ensure `supabase start` is running
- **Auth errors**: Tests may need valid JWT tokens for authenticated endpoints

### Batch Tests

- **Import errors**: Ensure you're in the `batch/` directory with venv activated
- **Async test failures**: Ensure `pytest-asyncio` is installed and `@pytest.mark.asyncio` decorator is used
