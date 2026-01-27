/**
 * API Contract Tests
 * 
 * These tests validate that API responses conform to the expected TypeScript types.
 * They ensure the contract between frontend and backend is maintained.
 */

import { assertEquals, assertExists, assert } from "https://deno.land/std@0.168.0/testing/asserts.ts";
import { fetchFunction, assertHasCorsHeaders } from "./test_utils.ts";

// ============================================================================
// Schema Validators
// ============================================================================

type ValidationResult = { valid: true } | { valid: false; errors: string[] };

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number";
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === "boolean";
}

function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function _isOptional<T>(value: unknown, validator: (v: unknown) => v is T): boolean {
  return value === undefined || value === null || validator(value);
}

// Suppress unused warning - kept for potential future use
void _isOptional;

function isStringArray(value: unknown): value is string[] {
  return isArray(value) && value.every(isString);
}

// ============================================================================
// Type Schemas matching www/src/types/index.ts
// ============================================================================

interface SchemaField {
  required: boolean;
  validator: (value: unknown) => boolean;
  description: string;
}

type Schema = Record<string, SchemaField>;

function validateSchema(obj: unknown, schema: Schema, path = ""): ValidationResult {
  const errors: string[] = [];

  if (!isObject(obj)) {
    return { valid: false, errors: [`${path || "root"}: expected object, got ${typeof obj}`] };
  }

  for (const [key, field] of Object.entries(schema)) {
    const value = obj[key];
    const fieldPath = path ? `${path}.${key}` : key;

    if (field.required && (value === undefined || value === null)) {
      errors.push(`${fieldPath}: required field is missing (${field.description})`);
      continue;
    }

    if (value !== undefined && value !== null && !field.validator(value)) {
      errors.push(`${fieldPath}: invalid value type (expected ${field.description}, got ${typeof value})`);
    }
  }

  return errors.length === 0 ? { valid: true } : { valid: false, errors };
}

// Search Response Schema
const CaseResultSchema: Schema = {
  id: { required: true, validator: isString, description: "string (UUID)" },
  neutral_citation: { required: true, validator: isString, description: "string" },
  case_name: { required: true, validator: isString, description: "string" },
  court_id: { required: true, validator: isString, description: "string" },
  court_name: { required: false, validator: isString, description: "string" },
  decision_date: { required: true, validator: isString, description: "string (date)" },
  headnote: { required: false, validator: isString, description: "string" },
  chunk_index: { required: false, validator: isNumber, description: "number" },
  chunk_text: { required: false, validator: isString, description: "string" },
  similarity_score: { required: false, validator: isNumber, description: "number" },
  fts_score: { required: false, validator: isNumber, description: "number" },
  combined_score: { required: false, validator: isNumber, description: "number" },
};

const LegislationResultSchema: Schema = {
  id: { required: true, validator: isString, description: "string (UUID)" },
  chapter_number: { required: true, validator: isString, description: "string" },
  title_en: { required: true, validator: isString, description: "string" },
  title_zh: { required: false, validator: isString, description: "string" },
  type: { required: true, validator: isString, description: "string" },
  status: { required: true, validator: isString, description: "string" },
  section_number: { required: false, validator: isString, description: "string" },
  section_title: { required: false, validator: isString, description: "string" },
  content_snippet: { required: false, validator: isString, description: "string" },
  chunk_index: { required: false, validator: isNumber, description: "number" },
  chunk_text: { required: false, validator: isString, description: "string" },
  similarity_score: { required: false, validator: isNumber, description: "number" },
  fts_score: { required: false, validator: isNumber, description: "number" },
  combined_score: { required: false, validator: isNumber, description: "number" },
};

const TimingSchema: Schema = {
  embedding_ms: { required: true, validator: isNumber, description: "number" },
  search_ms: { required: true, validator: isNumber, description: "number" },
  total_ms: { required: true, validator: isNumber, description: "number" },
};

const SearchResponseSchema: Schema = {
  results: { required: true, validator: isArray, description: "array" },
  query: { required: true, validator: isString, description: "string" },
  searchMode: { required: true, validator: isString, description: "string (semantic|hybrid|keyword)" },
  type: { required: true, validator: isString, description: "string (cases|legislation|all)" },
  total: { required: false, validator: isNumber, description: "number" },
  timing: { required: true, validator: isObject, description: "Timing object" },
};

// Suggestions Response Schema
const SuggestionSchema: Schema = {
  text: { required: true, validator: isString, description: "string" },
  type: { required: true, validator: isString, description: "string (citation|case_name|legislation|legal_term)" },
};

const SuggestionsResponseSchema: Schema = {
  suggestions: { required: true, validator: isArray, description: "array of Suggestion" },
};

// Case Detail Schema
const CourtSchema: Schema = {
  id: { required: true, validator: isString, description: "string" },
  name_en: { required: true, validator: isString, description: "string" },
  code: { required: true, validator: isString, description: "string" },
};

const CaseDetailSchema: Schema = {
  id: { required: true, validator: isString, description: "string (UUID)" },
  neutral_citation: { required: true, validator: isString, description: "string" },
  case_number: { required: false, validator: isString, description: "string" },
  case_name: { required: true, validator: isString, description: "string" },
  court: { required: true, validator: isObject, description: "Court object" },
  decision_date: { required: true, validator: isString, description: "string (date)" },
  judges: { required: false, validator: isStringArray, description: "string[]" },
  parties: { required: false, validator: isObject, description: "Parties object" },
  headnote: { required: false, validator: isString, description: "string" },
  full_text: { required: false, validator: isString, description: "string" },
  source_url: { required: false, validator: isString, description: "string (URL)" },
  pdf_url: { required: false, validator: isString, description: "string (URL)" },
};

// Citations Response Schema
const CitedCaseSchema: Schema = {
  id: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
  citation_text: { required: true, validator: isString, description: "string" },
  cited_case_name: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
  neutral_citation: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
  case_name: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
  court_code: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
  decision_date: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
  is_in_database: { required: true, validator: isBoolean, description: "boolean" },
};

const CitingCaseSchema: Schema = {
  id: { required: true, validator: isString, description: "string (UUID)" },
  neutral_citation: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
  case_name: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
  court_code: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
  decision_date: { required: false, validator: (v) => v === null || isString(v), description: "string | null" },
};

const CitationsResponseSchema: Schema = {
  cited_cases: { required: true, validator: isArray, description: "array of CitedCase" },
  citing_cases: { required: true, validator: isArray, description: "array of CitingCase" },
};

// Legislation Detail Schema
const LegislationSectionSchema: Schema = {
  id: { required: true, validator: isString, description: "string (UUID)" },
  section_number: { required: true, validator: isString, description: "string" },
  title: { required: false, validator: isString, description: "string" },
  content: { required: true, validator: isString, description: "string" },
};

const LegislationScheduleSchema: Schema = {
  id: { required: true, validator: isString, description: "string (UUID)" },
  schedule_number: { required: true, validator: isString, description: "string" },
  title: { required: false, validator: isString, description: "string" },
  content: { required: true, validator: isString, description: "string" },
};

const LegislationDetailSchema: Schema = {
  id: { required: true, validator: isString, description: "string (UUID)" },
  chapter_number: { required: true, validator: isString, description: "string" },
  title_en: { required: true, validator: isString, description: "string" },
  title_zh: { required: false, validator: isString, description: "string" },
  type: { required: true, validator: isString, description: "string" },
  status: { required: true, validator: isString, description: "string" },
  commencement_date: { required: false, validator: isString, description: "string (date)" },
  source_url: { required: false, validator: isString, description: "string (URL)" },
  sections: { required: true, validator: isArray, description: "array of LegislationSection" },
  schedules: { required: true, validator: isArray, description: "array of LegislationSchedule" },
};

// Error Response Schema
const ErrorResponseSchema: Schema = {
  error: { required: true, validator: isObject, description: "Error object" },
};

const ErrorObjectSchema: Schema = {
  code: { required: true, validator: isString, description: "string (error code)" },
  message: { required: true, validator: isString, description: "string (error message)" },
};

// ============================================================================
// Contract Tests
// ============================================================================

Deno.test("Contract - Search response matches SearchResponse type", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "contract law",
      type: "cases",
      options: { limit: 5, searchMode: "semantic" },
    },
  });

  assertHasCorsHeaders(response);

  if (response.status === 200) {
    const body = await response.json();
    
    // Validate top-level SearchResponse schema
    const result = validateSchema(body, SearchResponseSchema);
    assert(result.valid, `SearchResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);

    // Validate timing object
    const timingResult = validateSchema((body as Record<string, unknown>).timing, TimingSchema);
    assert(timingResult.valid, `Timing schema validation failed: ${timingResult.valid ? "" : timingResult.errors.join(", ")}`);

    // Validate each result matches CaseResult schema (since type: "cases")
    const results = (body as Record<string, unknown>).results as unknown[];
    for (let i = 0; i < results.length; i++) {
      const caseResult = validateSchema(results[i], CaseResultSchema, `results[${i}]`);
      assert(caseResult.valid, `CaseResult schema validation failed: ${caseResult.valid ? "" : caseResult.errors.join(", ")}`);
    }

    // Validate searchMode is valid enum value
    const searchMode = (body as Record<string, unknown>).searchMode;
    assert(
      searchMode === "semantic" || searchMode === "hybrid" || searchMode === "keyword",
      `Invalid searchMode: ${searchMode}`
    );

    // Validate type is valid enum value
    const type = (body as Record<string, unknown>).type;
    assert(
      type === "cases" || type === "legislation" || type === "all",
      `Invalid type: ${type}`
    );
  } else {
    // Validate error response schema
    const body = await response.json();
    const result = validateSchema(body, ErrorResponseSchema);
    assert(result.valid, `ErrorResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);
    console.log("Search returned error (may be expected if AWS not configured):", body);
  }
});

Deno.test("Contract - Suggestions response matches SuggestionsResponse type", async () => {
  const response = await fetchFunction("suggestions", {
    method: "GET",
    params: { q: "negligence" },
  });

  // Handle auth not available in local testing
  if (response.status === 401) {
    await response.body?.cancel();
    console.log("Skipping suggestions contract test - auth not available");
    return;
  }

  assertEquals(response.status, 200);
  assertHasCorsHeaders(response);

  const body = await response.json();

  // Validate top-level SuggestionsResponse schema
  const result = validateSchema(body, SuggestionsResponseSchema);
  assert(result.valid, `SuggestionsResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);

  // Validate each suggestion matches Suggestion schema
  const suggestions = (body as Record<string, unknown>).suggestions as unknown[];
  for (let i = 0; i < suggestions.length; i++) {
    const suggestionResult = validateSchema(suggestions[i], SuggestionSchema, `suggestions[${i}]`);
    assert(suggestionResult.valid, `Suggestion schema validation failed: ${suggestionResult.valid ? "" : suggestionResult.errors.join(", ")}`);

    // Validate type is valid enum value
    const suggestionType = (suggestions[i] as Record<string, unknown>).type;
    assert(
      suggestionType === "citation" || suggestionType === "case_name" || 
      suggestionType === "legislation" || suggestionType === "legal_term",
      `Invalid suggestion type: ${suggestionType}`
    );
  }
});

Deno.test("Contract - Error response matches error schema", async () => {
  const response = await fetchFunction("cases/invalid-uuid", { method: "GET" });

  // Handle auth not available - still validates error schema
  if (response.status === 401) {
    const body = await response.json();
    const result = validateSchema(body, ErrorResponseSchema);
    assert(result.valid, `ErrorResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);
    return;
  }

  assertEquals(response.status, 400);
  assertHasCorsHeaders(response);

  const body = await response.json();

  // Validate error response schema
  const result = validateSchema(body, ErrorResponseSchema);
  assert(result.valid, `ErrorResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);

  // Validate error object schema
  const errorObj = (body as Record<string, unknown>).error;
  const errorResult = validateSchema(errorObj, ErrorObjectSchema);
  assert(errorResult.valid, `Error object schema validation failed: ${errorResult.valid ? "" : errorResult.errors.join(", ")}`);
});

Deno.test("Contract - 404 error response has correct structure", async () => {
  const response = await fetchFunction("cases/00000000-0000-0000-0000-000000000000", {
    method: "GET",
  });

  // Handle auth not available
  if (response.status === 401) {
    const body = await response.json();
    const result = validateSchema(body, ErrorResponseSchema);
    assert(result.valid, `ErrorResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);
    console.log("Skipping 404 test - auth not available, but error schema validated");
    return;
  }

  assertEquals(response.status, 404);

  const body = await response.json();

  // Validate error response schema
  const result = validateSchema(body, ErrorResponseSchema);
  assert(result.valid, `ErrorResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);

  const errorObj = (body as Record<string, unknown>).error as Record<string, unknown>;
  assertEquals(errorObj.code, "NOT_FOUND");
  assertExists(errorObj.message);
});

Deno.test("Contract - Search with legislation type returns LegislationResult schema", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "companies ordinance",
      type: "legislation",
      options: { limit: 5, searchMode: "semantic" },
    },
  });

  if (response.status === 200) {
    const body = await response.json();

    // Validate top-level SearchResponse schema
    const result = validateSchema(body, SearchResponseSchema);
    assert(result.valid, `SearchResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);

    // Validate each result matches LegislationResult schema
    const results = (body as Record<string, unknown>).results as unknown[];
    for (let i = 0; i < results.length; i++) {
      const legResult = validateSchema(results[i], LegislationResultSchema, `results[${i}]`);
      assert(legResult.valid, `LegislationResult schema validation failed: ${legResult.valid ? "" : legResult.errors.join(", ")}`);
    }

    assertEquals((body as Record<string, unknown>).type, "legislation");
  } else {
    await response.body?.cancel();
    console.log("Legislation search returned non-200 (may be expected if AWS not configured)");
  }
});

Deno.test("Contract - Search timing values are non-negative numbers", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "breach of contract",
      type: "cases",
      options: { limit: 1 },
    },
  });

  if (response.status === 200) {
    const body = await response.json() as { timing: { embedding_ms: number; search_ms: number; total_ms: number } };

    assert(body.timing.embedding_ms >= 0, "embedding_ms should be non-negative");
    assert(body.timing.search_ms >= 0, "search_ms should be non-negative");
    assert(body.timing.total_ms >= 0, "total_ms should be non-negative");
    assert(
      body.timing.total_ms >= body.timing.embedding_ms,
      "total_ms should be >= embedding_ms"
    );
  } else {
    await response.body?.cancel();
  }
});

Deno.test("Contract - Suggestions with type filter returns filtered results", async () => {
  const response = await fetchFunction("suggestions", {
    method: "GET",
    params: { q: "contract", type: "cases" },
  });

  // Handle auth not available
  if (response.status === 401) {
    await response.body?.cancel();
    console.log("Skipping suggestions filter test - auth not available");
    return;
  }

  assertEquals(response.status, 200);

  const body = await response.json();
  const result = validateSchema(body, SuggestionsResponseSchema);
  assert(result.valid, `SuggestionsResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);
});

Deno.test("Contract - Empty suggestions array is valid", async () => {
  const response = await fetchFunction("suggestions", {
    method: "GET",
    params: { q: "x" }, // Single char returns empty
  });

  // Handle auth not available
  if (response.status === 401) {
    await response.body?.cancel();
    console.log("Skipping empty suggestions test - auth not available");
    return;
  }

  assertEquals(response.status, 200);

  const body = await response.json() as { suggestions: unknown[] };
  
  // Validate schema even for empty results
  const result = validateSchema(body, SuggestionsResponseSchema);
  assert(result.valid, `SuggestionsResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);
  
  assertEquals(body.suggestions.length, 0);
});

Deno.test("Contract - Search request validation returns proper error", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      // Missing required 'query' field
      type: "cases",
    },
  });

  // Handle auth not available - still validates error schema
  if (response.status === 401) {
    const body = await response.json();
    const result = validateSchema(body, ErrorResponseSchema);
    assert(result.valid, `ErrorResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);
    console.log("Skipping search validation test - auth not available, but error schema validated");
    return;
  }

  assertEquals(response.status, 400);

  const body = await response.json();
  const result = validateSchema(body, ErrorResponseSchema);
  assert(result.valid, `ErrorResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);

  const errorObj = (body as Record<string, unknown>).error as Record<string, unknown>;
  assertExists(errorObj.message);
});

Deno.test("Contract - Citations endpoint returns CitationsResponse schema", async () => {
  // First, we need a valid case ID. Try to get one from search.
  const searchResponse = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "negligence",
      type: "cases",
      options: { limit: 1 },
    },
  });

  if (searchResponse.status !== 200) {
    await searchResponse.body?.cancel();
    console.log("Skipping citations contract test - search not available");
    return;
  }

  const searchBody = await searchResponse.json() as { results: Array<{ id: string }> };
  
  if (searchBody.results.length === 0) {
    console.log("Skipping citations contract test - no cases found");
    return;
  }

  const caseId = searchBody.results[0].id;
  const response = await fetchFunction(`cases/${caseId}/citations`, { method: "GET" });

  if (response.status === 200) {
    const body = await response.json();

    // Validate CitationsResponse schema
    const result = validateSchema(body, CitationsResponseSchema);
    assert(result.valid, `CitationsResponse schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);

    // Validate each cited case
    const citedCases = (body as Record<string, unknown>).cited_cases as unknown[];
    for (let i = 0; i < citedCases.length; i++) {
      const citedResult = validateSchema(citedCases[i], CitedCaseSchema, `cited_cases[${i}]`);
      assert(citedResult.valid, `CitedCase schema validation failed: ${citedResult.valid ? "" : citedResult.errors.join(", ")}`);
    }

    // Validate each citing case
    const citingCases = (body as Record<string, unknown>).citing_cases as unknown[];
    for (let i = 0; i < citingCases.length; i++) {
      const citingResult = validateSchema(citingCases[i], CitingCaseSchema, `citing_cases[${i}]`);
      assert(citingResult.valid, `CitingCase schema validation failed: ${citingResult.valid ? "" : citingResult.errors.join(", ")}`);
    }
  } else {
    await response.body?.cancel();
    console.log("Citations endpoint returned non-200");
  }
});

Deno.test("Contract - Case detail returns CaseDetail schema", async () => {
  // First, get a valid case ID from search
  const searchResponse = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "judicial review",
      type: "cases",
      options: { limit: 1 },
    },
  });

  if (searchResponse.status !== 200) {
    await searchResponse.body?.cancel();
    console.log("Skipping case detail contract test - search not available");
    return;
  }

  const searchBody = await searchResponse.json() as { results: Array<{ id: string }> };
  
  if (searchBody.results.length === 0) {
    console.log("Skipping case detail contract test - no cases found");
    return;
  }

  const caseId = searchBody.results[0].id;
  const response = await fetchFunction(`cases/${caseId}`, { method: "GET" });

  if (response.status === 200) {
    const body = await response.json();

    // Validate CaseDetail schema
    const result = validateSchema(body, CaseDetailSchema);
    assert(result.valid, `CaseDetail schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);

    // Validate nested court object
    const court = (body as Record<string, unknown>).court;
    const courtResult = validateSchema(court, CourtSchema);
    assert(courtResult.valid, `Court schema validation failed: ${courtResult.valid ? "" : courtResult.errors.join(", ")}`);
  } else {
    await response.body?.cancel();
    console.log("Case detail endpoint returned non-200");
  }
});

Deno.test("Contract - Search hybrid mode includes correct searchMode", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "employment law",
      type: "all",
      options: { searchMode: "hybrid", semanticWeight: 0.7 },
    },
  });

  if (response.status === 200) {
    const body = await response.json() as { searchMode: string; type: string };
    
    assertEquals(body.searchMode, "hybrid");
    assertEquals(body.type, "all");
  } else {
    await response.body?.cancel();
  }
});

Deno.test("Contract - Search results have consistent score fields", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "tort law",
      type: "cases",
      options: { searchMode: "hybrid", limit: 5 },
    },
  });

  if (response.status === 200) {
    const body = await response.json() as { results: Array<Record<string, unknown>> };

    for (const result of body.results) {
      // In hybrid mode, results should have combined_score
      if (result.combined_score !== undefined) {
        assert(isNumber(result.combined_score), "combined_score should be a number");
        assert(result.combined_score >= 0, "combined_score should be non-negative");
      }

      // Similarity score should be between 0 and 1 if present
      if (result.similarity_score !== undefined) {
        assert(isNumber(result.similarity_score), "similarity_score should be a number");
        assert(
          result.similarity_score >= 0 && result.similarity_score <= 1,
          "similarity_score should be between 0 and 1"
        );
      }
    }
  } else {
    await response.body?.cancel();
  }
});

Deno.test("Contract - Legislation detail returns LegislationDetail schema", async () => {
  // First, get a valid legislation ID from search
  const searchResponse = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "companies ordinance",
      type: "legislation",
      options: { limit: 1 },
    },
  });

  if (searchResponse.status !== 200) {
    await searchResponse.body?.cancel();
    console.log("Skipping legislation detail contract test - search not available");
    return;
  }

  const searchBody = await searchResponse.json() as { results: Array<{ id: string }> };
  
  if (searchBody.results.length === 0) {
    console.log("Skipping legislation detail contract test - no legislation found");
    return;
  }

  const legislationId = searchBody.results[0].id;
  const response = await fetchFunction(`legislation/${legislationId}`, { method: "GET" });

  if (response.status === 200) {
    const body = await response.json();

    // Validate LegislationDetail schema
    const result = validateSchema(body, LegislationDetailSchema);
    assert(result.valid, `LegislationDetail schema validation failed: ${result.valid ? "" : result.errors.join(", ")}`);

    // Validate sections array
    const sections = (body as Record<string, unknown>).sections as unknown[];
    for (let i = 0; i < sections.length; i++) {
      const sectionResult = validateSchema(sections[i], LegislationSectionSchema, `sections[${i}]`);
      assert(sectionResult.valid, `LegislationSection schema validation failed: ${sectionResult.valid ? "" : sectionResult.errors.join(", ")}`);
    }

    // Validate schedules array
    const schedules = (body as Record<string, unknown>).schedules as unknown[];
    for (let i = 0; i < schedules.length; i++) {
      const scheduleResult = validateSchema(schedules[i], LegislationScheduleSchema, `schedules[${i}]`);
      assert(scheduleResult.valid, `LegislationSchedule schema validation failed: ${scheduleResult.valid ? "" : scheduleResult.errors.join(", ")}`);
    }
  } else {
    await response.body?.cancel();
    console.log("Legislation detail endpoint returned non-200");
  }
});
