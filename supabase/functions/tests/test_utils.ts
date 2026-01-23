export const TEST_BASE_URL = Deno.env.get("SUPABASE_URL") || "http://127.0.0.1:34321";
export const TEST_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0";
export const TEST_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU";

function base64UrlEncode(input: string): string {
  return btoa(input).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function createTestJwt(options: { sub?: string; expSecondsFromNow?: number } = {}): string {
  const header = base64UrlEncode(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = base64UrlEncode(
    JSON.stringify({
      sub: options.sub ?? "test-user",
      exp: Math.floor(Date.now() / 1000) + (options.expSecondsFromNow ?? 60 * 60),
      role: "authenticated",
    })
  );

  // Signature is not verified in local tests (verifyAuthHeader only decodes payload)
  return `${header}.${payload}.test-signature`;
}

export function functionsUrl(functionName: string): string {
  return `${TEST_BASE_URL}/functions/v1/${functionName}`;
}

export function createHeaders(options: { auth?: string; contentType?: string } = {}): Headers {
  const headers = new Headers();
  headers.set("Content-Type", options.contentType || "application/json");
  if (options.auth) {
    headers.set("Authorization", `Bearer ${options.auth}`);
  }
  return headers;
}

export function fetchFunction(
  functionName: string,
  options: {
    method?: string;
    body?: unknown;
    auth?: string;
    params?: Record<string, string>;
  } = {}
): Promise<Response> {
  let url = functionsUrl(functionName);
  
  if (options.params) {
    const searchParams = new URLSearchParams(options.params);
    url += `?${searchParams.toString()}`;
  }

  const auth = options.auth ?? createTestJwt();

  const fetchOptions: RequestInit = {
    method: options.method || "GET",
    headers: createHeaders({ auth }),
  };

  if (options.body && options.method !== "GET") {
    fetchOptions.body = JSON.stringify(options.body);
  }

  return fetch(url, fetchOptions);
}

export async function assertJsonResponse(
  response: Response,
  expectedStatus: number
): Promise<unknown> {
  if (response.status !== expectedStatus) {
    const text = await response.text();
    throw new Error(`Expected status ${expectedStatus}, got ${response.status}: ${text}`);
  }
  return response.json();
}

export function assertHasCorsHeaders(response: Response): void {
  const corsOrigin = response.headers.get("Access-Control-Allow-Origin");
  if (corsOrigin !== "*") {
    throw new Error(`Expected CORS header Access-Control-Allow-Origin: *, got: ${corsOrigin}`);
  }
}
