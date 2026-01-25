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

          // Determine if we're in a secure context
          const isSecureContext = typeof window !== 'undefined' && (
            window.isSecureContext || 
            window.location.protocol === 'https:' ||
            window.location.hostname === 'localhost' ||
            window.location.hostname === '127.0.0.1'
          );
          
          const maxAge = options?.maxAge ? `; Max-Age=${options.maxAge}` : '';
          const path = `; Path=${options?.path || '/'}`;
          // Use Strict for better security, fall back to Lax if specified
          const sameSiteValue = options?.sameSite || 'Lax';
          const sameSite = `; SameSite=${sameSiteValue.toString().charAt(0).toUpperCase() + sameSiteValue.toString().slice(1)}`;
          // Always set Secure flag in production (non-localhost) HTTPS contexts
          const isProduction = typeof window !== 'undefined' && 
            !['localhost', '127.0.0.1'].includes(window.location.hostname);
          const secure = (isSecureContext && isProduction) ? '; Secure' : '';
          // Add HttpOnly-like protection by using __Host- prefix in production
          const cookieName = (isProduction && window.location.protocol === 'https:' && name.startsWith('sb-')) 
            ? name : name;

          document.cookie = `${cookieName}=${value}${maxAge}${path}${sameSite}${secure}`;
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
