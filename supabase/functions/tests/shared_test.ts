import { assertEquals, assertExists } from "https://deno.land/std@0.168.0/testing/asserts.ts";
import { corsHeaders, handleCors } from "../_shared/cors.ts";
import { badRequest, unauthorized, notFound, serverError } from "../_shared/errors.ts";

Deno.test("CORS - corsHeaders contains required headers", () => {
  assertEquals(corsHeaders["Access-Control-Allow-Origin"], "*");
  assertExists(corsHeaders["Access-Control-Allow-Headers"]);
  assertExists(corsHeaders["Access-Control-Allow-Methods"]);
});

Deno.test("CORS - corsHeaders allows required methods", () => {
  const methods = corsHeaders["Access-Control-Allow-Methods"];
  assertEquals(methods.includes("GET"), true);
  assertEquals(methods.includes("POST"), true);
  assertEquals(methods.includes("OPTIONS"), true);
});

Deno.test("CORS - corsHeaders allows authorization header", () => {
  const headers = corsHeaders["Access-Control-Allow-Headers"];
  assertEquals(headers.includes("authorization"), true);
  assertEquals(headers.includes("content-type"), true);
});

Deno.test("CORS - handleCors returns response for OPTIONS", () => {
  const req = new Request("http://localhost/test", { method: "OPTIONS" });
  const response = handleCors(req);
  
  assertExists(response);
  assertEquals(response?.status, 200);
});

Deno.test("CORS - handleCors returns null for non-OPTIONS", () => {
  const getReq = new Request("http://localhost/test", { method: "GET" });
  const postReq = new Request("http://localhost/test", { method: "POST" });
  
  assertEquals(handleCors(getReq), null);
  assertEquals(handleCors(postReq), null);
});

Deno.test("Errors - badRequest returns 400 status", async () => {
  const response = badRequest("Invalid input");
  
  assertEquals(response.status, 400);
  const body = await response.json() as { error: { code: string; message: string } };
  assertEquals(body.error.code, "BAD_REQUEST");
  assertEquals(body.error.message, "Invalid input");
});

Deno.test("Errors - badRequest includes details when provided", async () => {
  const response = badRequest("Validation failed", { field: "email" });
  
  const body = await response.json() as { error: { details: { field: string } } };
  assertEquals(body.error.details.field, "email");
});

Deno.test("Errors - unauthorized returns 401 status", async () => {
  const response = unauthorized("Token expired");
  
  assertEquals(response.status, 401);
  const body = await response.json() as { error: { code: string; message: string } };
  assertEquals(body.error.code, "UNAUTHORIZED");
  assertEquals(body.error.message, "Token expired");
});

Deno.test("Errors - unauthorized uses default message", async () => {
  const response = unauthorized();
  
  const body = await response.json() as { error: { message: string } };
  assertEquals(body.error.message, "Unauthorized");
});

Deno.test("Errors - notFound returns 404 status", async () => {
  const response = notFound("Case not found");
  
  assertEquals(response.status, 404);
  const body = await response.json() as { error: { code: string; message: string } };
  assertEquals(body.error.code, "NOT_FOUND");
  assertEquals(body.error.message, "Case not found");
});

Deno.test("Errors - notFound uses default message", async () => {
  const response = notFound();
  
  const body = await response.json() as { error: { message: string } };
  assertEquals(body.error.message, "Resource not found");
});

Deno.test("Errors - serverError returns 500 status", async () => {
  const response = serverError("Database connection failed");
  
  assertEquals(response.status, 500);
  const body = await response.json() as { error: { code: string; message: string } };
  assertEquals(body.error.code, "INTERNAL_ERROR");
  assertEquals(body.error.message, "Database connection failed");
});

Deno.test("Errors - serverError uses default message", async () => {
  const response = serverError();
  
  const body = await response.json() as { error: { message: string } };
  assertEquals(body.error.message, "Internal server error");
});

Deno.test("Errors - all error responses include CORS headers", async () => {
  const responses = [
    badRequest("test"),
    unauthorized("test"),
    notFound("test"),
    serverError("test"),
  ];
  
  for (const response of responses) {
    assertEquals(response.headers.get("Access-Control-Allow-Origin"), "*");
    assertEquals(response.headers.get("Content-Type"), "application/json");
    await response.body?.cancel();
  }
});
