import { assertEquals } from "https://deno.land/std@0.168.0/testing/asserts.ts";
import { fetchFunction, assertHasCorsHeaders } from "./test_utils.ts";

Deno.test("Legislation - OPTIONS returns CORS headers", async () => {
  const response = await fetch("http://127.0.0.1:34321/functions/v1/legislation", {
    method: "OPTIONS",
  });
  
  assertEquals(response.status, 200);
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});

Deno.test("Legislation - POST method not allowed", async () => {
  const response = await fetchFunction("legislation", { method: "POST", body: {} });
  
  assertEquals(response.status, 400);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "BAD_REQUEST");
});

Deno.test("Legislation - invalid UUID returns error", async () => {
  const response = await fetchFunction("legislation/invalid-id", { method: "GET" });
  
  assertEquals(response.status, 400);
  const body = await response.json() as { error: { message: string } };
  assertEquals(body.error.message, "Invalid legislation ID. Must be a valid UUID.");
});

Deno.test("Legislation - non-existent UUID returns 404", async () => {
  const response = await fetchFunction("legislation/00000000-0000-0000-0000-000000000000", {
    method: "GET",
  });
  
  assertEquals(response.status, 404);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "NOT_FOUND");
});

Deno.test("Legislation - valid request has CORS headers", async () => {
  const response = await fetchFunction("legislation/00000000-0000-0000-0000-000000000000", {
    method: "GET",
  });
  
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});
