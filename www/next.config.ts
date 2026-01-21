import type { NextConfig } from "next";
import { config } from "dotenv";
import { resolve } from "path";

// Load environment variables from root .env file
config({ path: resolve(__dirname, "../.env") });

const supabaseUrl = process.env.SUPABASE_URL || "http://127.0.0.1:34321";
const supabaseOrigin = new URL(supabaseUrl);

const nextConfig: NextConfig = {
  reactCompiler: true,
  async rewrites() {
    return [
      {
        source: "/auth/v1/:path*",
        destination: `${supabaseOrigin.protocol}//${supabaseOrigin.host}/auth/v1/:path*`,
      },
      {
        source: "/rest/v1/:path*",
        destination: `${supabaseOrigin.protocol}//${supabaseOrigin.host}/rest/v1/:path*`,
      },
      {
        source: "/storage/v1/:path*",
        destination: `${supabaseOrigin.protocol}//${supabaseOrigin.host}/storage/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
