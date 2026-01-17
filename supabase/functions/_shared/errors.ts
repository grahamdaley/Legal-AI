import { corsHeaders } from "./cors.ts";

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

function errorResponse(
  status: number,
  code: string,
  message: string,
  details?: unknown
): Response {
  const error: ErrorResponse["error"] = { code, message };
  if (details !== undefined) {
    error.details = details;
  }
  const body: ErrorResponse = { error };
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

export function badRequest(message: string, details?: unknown): Response {
  return errorResponse(400, "BAD_REQUEST", message, details);
}

export function unauthorized(message = "Unauthorized"): Response {
  return errorResponse(401, "UNAUTHORIZED", message);
}

export function notFound(message = "Resource not found"): Response {
  return errorResponse(404, "NOT_FOUND", message);
}

export function serverError(
  message = "Internal server error",
  details?: unknown
): Response {
  return errorResponse(500, "INTERNAL_ERROR", message, details);
}
