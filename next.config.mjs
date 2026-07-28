/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // In production Vercel routes /api/* to the Python serverless function directly
    // (via vercel.json functions config), bypassing Next.js entirely.
    // This rewrite only matters for local `next dev` / `vercel dev`.
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
