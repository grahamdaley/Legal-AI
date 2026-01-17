import { assertEquals } from "https://deno.land/std@0.168.0/testing/asserts.ts";
import { fetchFunction, assertHasCorsHeaders } from "./test_utils.ts";

Deno.test("Cases - OPTIONS returns CORS headers", async () => {
  const response = await fetch("http://127.0.0.1:34321/functions/v1/cases", {
    method: "OPTIONS",
  });
  
  assertEquals(response.status, 200);
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});

Deno.test("Cases - POST method not allowed", async () => {
  const response = await fetchFunction("cases", { method: "POST", body: {} });
  
  assertEquals(response.status, 400);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "BAD_REQUEST");
});

Deno.test("Cases - invalid UUID returns error", async () => {
  const response = await fetchFunction("cases/not-a-uuid", { method: "GET" });
  
  assertEquals(response.status, 400);
  const body = await response.json() as { error: { message: string } };
  assertEquals(body.error.message, "Invalid case ID. Must be a valid UUID.");
});

Deno.test("Cases - non-existent UUID returns 404", async () => {
  const response = await fetchFunction("cases/00000000-0000-0000-0000-000000000000", {
    method: "GET",
  });
  
  assertEquals(response.status, 404);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "NOT_FOUND");
});

Deno.test("Cases - valid request has CORS headers", async () => {
  const response = await fetchFunction("cases/00000000-0000-0000-0000-000000000000", {
    method: "GET",
  });
  
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});
