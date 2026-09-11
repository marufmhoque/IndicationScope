/** @type {import('next').NextConfig} */

// The app is served under this prefix on marufhoque.com — the portfolio proxies
// /tools/indicationscope/* straight through, preserving the prefix. basePath makes
// Next emit prefixed asset and route URLs; without it the JS bundles resolve to the
// domain root, 404, and React never hydrates (leaving the form inert).
//
// Kept in sync with the portfolio's vercel.json rewrite. Changing one without the
// other breaks the page.
const BASE_PATH = "/tools/indicationscope";

const nextConfig = {
  basePath: BASE_PATH,
  // No ESLint config or dependency exists in this project, so `next build`
  // was applying built-in defaults that error on patterns Next itself
  // requires — notably `export const metadata` in app/layout.tsx. That was
  // failing every production build, which is why deploys went stale.
  // Re-enable by adding eslint + eslint-config-next and a real config.
  eslint: {
    ignoreDuringBuilds: true,
  },
  // basePath does not prefix fetch(); client code reads this to build API URLs.
  env: {
    NEXT_PUBLIC_BASE_PATH: BASE_PATH,
  },
  async rewrites() {
    // In production Vercel routes /api/* to the Python serverless function directly
    // (via vercel.json rewrites), bypassing Next.js entirely.
    // This rewrite only matters for local `next dev` / `vercel dev`.
    //
    // Next automatically prefixes `source` with basePath, while leaving the external
    // destination untouched — so the local FastAPI server still sees a bare /api/*.
    if (process.env.NODE_ENV !== "development") {
      return [];
    }
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
