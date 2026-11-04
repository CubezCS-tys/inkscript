import type { NextApiRequest, NextApiResponse } from 'next';

// P1/P2 sign-in: the pasted token is checked against the Desk API (/me) and kept in an httpOnly cookie, which the
// /desk/api proxy forwards. TODO(P4): real accounts (invitation, password + TOTP, sessions, HTTPS).
const API = process.env.DESK_API_ORIGIN || 'http://127.0.0.1:8005';
const COOKIE = 'desk_token';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'DELETE') {
    res.setHeader('Set-Cookie', `${COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0`);
    return res.status(200).json({ ok: true });
  }
  if (req.method !== 'POST') return res.status(405).end();
  const token = String((req.body && req.body.token) || '').trim();
  if (!token || token.length > 200 || /[\s;,]/.test(token)) return res.status(400).json({ detail: 'paste the token' });
  const r = await fetch(`${API}/desk/api/me`, { headers: { 'X-Desk-Token': token } });
  if (!r.ok) return res.status(401).json({ detail: 'unknown or revoked token' });
  const me = await r.json();
  res.setHeader('Set-Cookie', `${COOKIE}=${token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${30 * 86400}`);
  return res.status(200).json({ actor_id: me.actor_id, role: me.role, name: me.name });
}
