import type { NextConfig } from "next";

const BACKEND = process.env.NEXT_PUBLIC_DEV_BACKEND ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  reactStrictMode: true,

  // Dev only: `next dev` proxies /api/* to a locally running FastAPI backend.
  // A static export ignores rewrites (production is same-origin, one port), so
  // they are omitted from the build to keep its output clean.
  ...(process.env.NODE_ENV === "development"
    ? {
        async rewrites() {
          return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
        },
      }
    : {}),
};

export default nextConfig;
