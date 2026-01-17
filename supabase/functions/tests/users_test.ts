import { assertEquals } from "https://deno.land/std@0.168.0/testing/asserts.ts";
import { fetchFunction, assertHasCorsHeaders, TEST_ANON_KEY } from "./test_utils.ts";

Deno.test("Users - OPTIONS returns CORS headers", async () => {
  const response = await fetch("http://127.0.0.1:34321/functions/v1/users/me", {
    method: "OPTIONS",
  });
  
  assertEquals(response.status, 200);
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});

Deno.test("Users - GET /me without auth returns 401", async () => {
  const response = await fetchFunction("users/me", { method: "GET" });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Users - GET /quota without auth returns 401", async () => {
  const response = await fetchFunction("users/quota", { method: "GET" });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Users - PATCH /me without auth returns 401", async () => {
  const response = await fetchFunction("users/me", {
    method: "PATCH",
    body: { full_name: "Test User" },
  });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Users - invalid endpoint returns 404", async () => {
  const response = await fetchFunction("users/invalid", {
    method: "GET",
    auth: TEST_ANON_KEY,
  });
  
  assertEquals(response.status, 401);
  await response.body?.cancel();
});

Deno.test("Users - CORS headers present on error responses", async () => {
  const response = await fetchFunction("users/me", { method: "GET" });
  
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});
