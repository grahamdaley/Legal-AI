import { assertEquals } from "https://deno.land/std@0.168.0/testing/asserts.ts";
import { fetchFunction, assertHasCorsHeaders, TEST_ANON_KEY } from "./test_utils.ts";

Deno.test("Collections - OPTIONS returns CORS headers", async () => {
  const response = await fetch("http://127.0.0.1:34321/functions/v1/collections", {
    method: "OPTIONS",
  });
  
  assertEquals(response.status, 200);
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});

Deno.test("Collections - GET without auth returns 401", async () => {
  const response = await fetchFunction("collections", { method: "GET" });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Collections - POST without auth returns 401", async () => {
  const response = await fetchFunction("collections", {
    method: "POST",
    body: { name: "Test Collection" },
  });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Collections - GET /:id without auth returns 401", async () => {
  const response = await fetchFunction("collections/00000000-0000-0000-0000-000000000000", {
    method: "GET",
  });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Collections - PATCH /:id without auth returns 401", async () => {
  const response = await fetchFunction("collections/00000000-0000-0000-0000-000000000000", {
    method: "PATCH",
    body: { name: "Updated Name" },
  });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Collections - DELETE /:id without auth returns 401", async () => {
  const response = await fetchFunction("collections/00000000-0000-0000-0000-000000000000", {
    method: "DELETE",
  });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Collections - POST /:id/items without auth returns 401", async () => {
  const response = await fetchFunction("collections/00000000-0000-0000-0000-000000000000/items", {
    method: "POST",
    body: { item_type: "case", item_id: "00000000-0000-0000-0000-000000000001" },
  });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Collections - invalid collection ID returns 401 without valid auth", async () => {
  const response = await fetchFunction("collections/not-a-uuid", {
    method: "GET",
    auth: TEST_ANON_KEY,
  });
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
});

Deno.test("Collections - CORS headers present on error responses", async () => {
  const response = await fetchFunction("collections", { method: "GET" });
  
  assertHasCorsHeaders(response);
  await response.body?.cancel();
});
