/** @type {import('next').NextConfig} */
// The Desk (experiment 49, P2). Served on 127.0.0.1:8004 only; the browser talks to this one port and Next
// proxies /desk/api/* to the Desk API on 127.0.0.1:8005 (cookies included, so ink crops load as plain <img>).
const API = process.env.DESK_API_ORIGIN || 'http://127.0.0.1:8005';
module.exports = {
  // a dev server for testing must not share .next with the live `next start` (next dev wipes it): NEXT_DIST_DIR=.next-dev-<port>
  distDir: process.env.NEXT_DIST_DIR || '.next',
  reactStrictMode: true,
  poweredByHeader: false,
  // keep /mockup/ and /mindmap/ at the exact paths the plain http.server served them
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return {
      beforeFiles: [
        // (the pages have no relative links, so /mockup and /mockup/ can serve the same file)
        // static pages in public/: /x and /x/ serve public/x/index.html
        { source: '/:page(mockup|mindmap|inventory|gate1|gate2|pitch)', destination: '/:page/index.html' },
        { source: '/:page(mockup|mindmap|inventory|gate1|gate2|pitch)/', destination: '/:page/index.html' },
      ],
      afterFiles: [
        { source: '/desk/api/:path*', destination: `${API}/desk/api/:path*` },
        // the article views (experiment 41/43/52 Layout pages, served by python http.server on 127.0.0.1:8899),
        // passed through so every page works through the one 9004 tunnel, whatever the host name (WSL: localhost)
        { source: '/views/:path*', destination: 'http://127.0.0.1:8899/:path*' },
      ],
    };
  },
  async headers() {
    return [{ source: '/:path*', headers: [
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Referrer-Policy', value: 'no-referrer' },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
    ] },
    // the classic article pages may be framed by the Desk itself (the article page's "Classic page" view), nobody else
    { source: '/views/:path*', headers: [{ key: 'X-Frame-Options', value: 'SAMEORIGIN' }] }];
  },
};
