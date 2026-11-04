// The browser talks to one port: /desk/api/* is proxied by Next to the Desk API (127.0.0.1:8005). The token rides
// in the httpOnly cookie set at sign-in; writes add X-Desk-Client (the API refuses a cookie write without it).
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

export async function api<T = any>(path: string, init: RequestInit & { json?: any } = {}): Promise<T> {
  const { json, ...rest } = init;
  const r = await fetch(`/desk/api${path}`, {
    credentials: 'same-origin',
    ...rest,
    method: rest.method || (json !== undefined ? 'POST' : 'GET'),
    headers: { 'X-Desk-Client': 'web', ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(rest.headers || {}) },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (r.status === 401 && typeof window !== 'undefined' && !window.location.pathname.startsWith('/signin')) {
    window.location.href = `/signin?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
  }
  if (r.status === 204) return null as T;
  let body: any = null;
  try { body = await r.json(); } catch { body = null; }
  if (!r.ok) {
    const d = body?.detail;
    throw new ApiError(r.status, typeof d === 'string' ? d : d ? JSON.stringify(d) : `${r.status} ${r.statusText}`);
  }
  return body as T;
}

export const enc = encodeURIComponent;

// an ink anchor '<stem>|p<page>|w<a>-<b>' -> its crop
export function cropOfAnchor(anchor?: string | null): string | null {
  if (!anchor) return null;
  const m = anchor.match(/^(.+)\|p(\d+)\|/);
  if (!m) return null;
  return `/desk/api/evidence/crop?stem=${enc(m[1])}&page=${m[2]}&anchor=${enc(anchor)}`;
}
export const cropOfBlock = (stem: string, page: number, block: string) =>
  `/desk/api/evidence/crop?stem=${enc(stem)}&page=${page}&block=${enc(block)}`;

// a subject key -> the page that shows it
export function hrefOf(key?: string | null): string | null {
  if (!key) return null;
  const i = key.indexOf(':');
  const kind = key.slice(0, i), val = key.slice(i + 1);
  if (kind === 'work') return `/works/${enc(val)}`;
  if (kind === 'person') return `/persons/${enc(val)}`;
  if (kind === 'article') return `/articles/${enc(val)}`;
  if (kind === 'mention') return `/articles/${enc(val.split('|')[0])}?tab=citations#${enc('m-' + val)}`;
  if (kind === 'byline') return `/articles/${enc(val.split('|')[0])}`;
  return null;
}

export const isArabic = (s?: string | null) => !!s && /[؀-ۿ]/.test(s) &&
  (s.match(/[؀-ۿ]/g) || []).length >= 0.3 * (s.match(/[\p{L}\p{N}]/gu) || []).length;
