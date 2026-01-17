import type { NextConfig } from "next";
import { config } from "dotenv";
import { resolve } from "path";

// Load environment variables from root .env file
config({ path: resolve(__dirname, "../.env") });

const nextConfig: NextConfig = {
  reactCompiler: true,
};

export default nextConfig;
