import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  // Use window.location.origin to make relative requests that will be proxied by Next.js
  const supabaseUrl = typeof window !== "undefined" 
    ? window.location.origin 
    : "http://localhost:3000"; // Fallback for SSR
  
  return createBrowserClient(
    supabaseUrl,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name) {
          if (typeof document === 'undefined') return undefined;
          const cookies = document.cookie.split('; ');
          const cookie = cookies.find(c => c.startsWith(`${name}=`));
          return cookie?.split('=')[1];
        },
        set(name, value, options) {
          if (typeof document === 'undefined') return;

          // Clear any prior cookie accidentally set on a narrow path like /login
          document.cookie = `${name}=; Max-Age=0; Path=/login`;

          const isHttps = typeof location !== 'undefined' && location.protocol === 'https:';
          const maxAge = options?.maxAge ? `; Max-Age=${options.maxAge}` : '';
          const path = `; Path=${options?.path || '/'}`;
          const sameSite = `; SameSite=${(options?.sameSite || 'Lax').toString().charAt(0).toUpperCase() + (options?.sameSite || 'Lax').toString().slice(1)}`;
          const secure = isHttps ? '; Secure' : '';

          document.cookie = `${name}=${value}${maxAge}${path}${sameSite}${secure}`;
        },
        remove(name, options) {
          if (typeof document === 'undefined') return;
          const path = `; Path=${options?.path || '/'}`;
          document.cookie = `${name}=; Max-Age=0${path}`;
          // Also clear potential narrow-path cookie
          document.cookie = `${name}=; Max-Age=0; Path=/login`;
        },
      },
    }
  );
}
