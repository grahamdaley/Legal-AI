import { assertEquals, assertExists } from "https://deno.land/std@0.168.0/testing/asserts.ts";
import { fetchFunction, assertHasCorsHeaders } from "./test_utils.ts";

Deno.test("Suggestions - OPTIONS returns CORS headers", async () => {
  const response = await fetch("http://127.0.0.1:34321/functions/v1/suggestions", {
    method: "OPTIONS",
  });
  
  assertEquals(response.status, 200);
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});

Deno.test("Suggestions - POST method not allowed", async () => {
  const response = await fetchFunction("suggestions", { method: "POST", body: {} });
  
  assertEquals(response.status, 400);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "BAD_REQUEST");
});

Deno.test("Suggestions - short query returns empty results", async () => {
  const response = await fetchFunction("suggestions", {
    method: "GET",
    params: { q: "a" },
  });
  
  assertEquals(response.status, 200);
  assertHasCorsHeaders(response);
  const body = await response.json() as { suggestions: unknown[] };
  assertEquals(body.suggestions.length, 0);
});

Deno.test("Suggestions - valid query returns suggestions array", async () => {
  const response = await fetchFunction("suggestions", {
    method: "GET",
    params: { q: "neg" },
  });
  
  assertEquals(response.status, 200);
  const body = await response.json() as { suggestions: Array<{ text: string; type: string }> };
  assertExists(body.suggestions);
  
  const hasNegligence = body.suggestions.some(s => s.text.toLowerCase().includes("neglig"));
  assertEquals(hasNegligence, true, "Should include negligence-related suggestions");
});

Deno.test("Suggestions - type filter for cases", async () => {
  const response = await fetchFunction("suggestions", {
    method: "GET",
    params: { q: "contract", type: "cases" },
  });
  
  assertEquals(response.status, 200);
  const body = await response.json() as { suggestions: unknown[] };
  assertExists(body.suggestions);
});

Deno.test("Suggestions - type filter for legislation", async () => {
  const response = await fetchFunction("suggestions", {
    method: "GET",
    params: { q: "companies", type: "legislation" },
  });
  
  assertEquals(response.status, 200);
  const body = await response.json() as { suggestions: unknown[] };
  assertExists(body.suggestions);
});

Deno.test("Suggestions - legal term suggestions included", async () => {
  const response = await fetchFunction("suggestions", {
    method: "GET",
    params: { q: "judicial" },
  });
  
  assertEquals(response.status, 200);
  const body = await response.json() as { suggestions: Array<{ text: string; type: string }> };
  
  const hasLegalTerm = body.suggestions.some(s => s.type === "legal_term");
  assertEquals(hasLegalTerm, true, "Should include legal term suggestions");
});

Deno.test("Suggestions - citation pattern matching", async () => {
  const response = await fetchFunction("suggestions", {
    method: "GET",
    params: { q: "[2024] HK" },
  });
  
  assertEquals(response.status, 200);
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});
