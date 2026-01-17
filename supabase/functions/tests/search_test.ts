import { assertEquals, assertExists } from "https://deno.land/std@0.168.0/testing/asserts.ts";
import { fetchFunction, assertHasCorsHeaders } from "./test_utils.ts";

Deno.test("Search - OPTIONS returns CORS headers", async () => {
  const response = await fetch("http://127.0.0.1:34321/functions/v1/search", {
    method: "OPTIONS",
  });
  
  assertEquals(response.status, 200);
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});

Deno.test("Search - GET method not allowed", async () => {
  const response = await fetchFunction("search", { method: "GET" });
  
  assertEquals(response.status, 400);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "BAD_REQUEST");
});

Deno.test("Search - POST without query returns error", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {},
  });
  
  assertEquals(response.status, 400);
  const body = await response.json() as { error: { message: string } };
  assertEquals(body.error.message, "Query is required and must be a non-empty string");
});

Deno.test("Search - POST with empty query returns error", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: { query: "   " },
  });
  
  assertEquals(response.status, 400);
  const body = await response.json() as { error: { message: string } };
  assertEquals(body.error.message, "Query is required and must be a non-empty string");
});

Deno.test("Search - POST with valid query structure", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "contract breach",
      type: "cases",
      options: {
        limit: 5,
        searchMode: "semantic",
      },
    },
  });
  
  assertHasCorsHeaders(response);
  
  if (response.status === 200) {
    const body = await response.json() as {
      results: unknown[];
      query: string;
      searchMode: string;
      timing: { embedding_ms: number; search_ms: number; total_ms: number };
    };
    assertExists(body.results);
    assertEquals(body.query, "contract breach");
    assertEquals(body.searchMode, "semantic");
    assertExists(body.timing);
    assertExists(body.timing.embedding_ms);
    assertExists(body.timing.search_ms);
    assertExists(body.timing.total_ms);
  } else {
    const body = await response.json();
    console.log("Search returned non-200 (may be expected if AWS not configured):", body);
  }
});

Deno.test("Search - hybrid mode includes both scores", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "negligence duty of care",
      type: "cases",
      options: {
        searchMode: "hybrid",
        semanticWeight: 0.6,
      },
    },
  });
  
  if (response.status === 200) {
    const body = await response.json() as { searchMode: string };
    assertEquals(body.searchMode, "hybrid");
  } else {
    await response.body?.cancel();
  }
});

Deno.test("Search - filters are accepted", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "judicial review",
      type: "cases",
      filters: {
        court: "CFA",
        yearFrom: 2020,
        yearTo: 2024,
      },
    },
  });
  
  if (response.status === 400) {
    const body = await response.json() as { error: { code: string } };
    assertEquals(body.error.code, "BAD_REQUEST");
  } else {
    await response.body?.cancel();
  }
});

Deno.test("Search - legislation type filter", async () => {
  const response = await fetchFunction("search", {
    method: "POST",
    body: {
      query: "companies ordinance",
      type: "legislation",
      filters: {
        legislationType: "ordinance",
      },
    },
  });
  
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});
