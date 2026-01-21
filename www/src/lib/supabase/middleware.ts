import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  });

  const path = request.nextUrl.pathname;
  const publicPaths = ["/", "/login", "/signup"];
  const isPublicPath = publicPaths.includes(path);

  // Fast-path: if an auth cookie is present, consider the request authenticated.
  // This avoids edge cases where the server cannot call /auth/v1/user during middleware.
  const hasAuthCookie = request.cookies.getAll().some((c) => /^(sb-.*-auth-token)$/.test(c.name) && c.value);
  if (hasAuthCookie) {
    // If authenticated and on an auth page -> redirect to /search
    if (path === "/login" || path === "/signup") {
      const url = request.nextUrl.clone();
      url.pathname = "/search";
      return NextResponse.redirect(url);
    }
    return supabaseResponse;
  }

  // Otherwise, fall back to Supabase user lookup
  const supabaseUrl = request.nextUrl.origin;

  const supabase = createServerClient(
    supabaseUrl,
    process.env.SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  // If not authenticated and requesting a protected path -> redirect to /login
  if (!user && !isPublicPath) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // If authenticated and on an auth page -> redirect to /search
  if (user && (path === "/login" || path === "/signup")) {
    const url = request.nextUrl.clone();
    url.pathname = "/search";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
