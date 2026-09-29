/** @type {import('next').NextConfig} */
const nextConfig = {
  agentRules: false,

  // In development, `next dev` does not run the Python functions in api/ --
  // Vercel does that in production. dev_api_server.py serves the same handlers
  // locally, and this rewrite points the browser at it. In a production build
  // no rewrite is emitted, so Vercel routes /api/* to the real functions.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    const port = process.env.DEV_API_PORT || "8787";
    return [{ source: "/api/:path*", destination: `http://127.0.0.1:${port}/api/:path*` }];
  },
};

export default nextConfig;
