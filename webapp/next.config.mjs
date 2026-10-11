/** @type {import('next').NextConfig} */
const nextConfig = {
  agentRules: false,
  async headers() {
    const dev = process.env.NODE_ENV === "development";
    return [{ source: "/:path*", headers: [
      { key: "Content-Security-Policy", value: `default-src 'self'; script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://tile.openstreetmap.org; font-src 'self'; connect-src 'self' https://tile.openstreetmap.org${dev ? " ws://127.0.0.1:3000" : ""}; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'` },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "geolocation=(self), camera=(), microphone=()" },
      { key: "Strict-Transport-Security", value: "max-age=31536000" },
    ] }];
  },

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
