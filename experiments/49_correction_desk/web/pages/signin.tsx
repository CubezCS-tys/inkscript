import React, { useState } from 'react';
import { useRouter } from 'next/router';
import { KeyRound, Info } from 'lucide-react';
import { S } from '../lib/strings';
import { ErrorBox } from '../components/Bits';

export default function SignIn() {
  const { query } = useRouter();
  const [tok, setTok] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const go = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('');
    const r = await fetch('/api/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: tok }) });
    setBusy(false);
    if (!r.ok) { setErr(S.signin.bad); return; }
    const next = typeof query.next === 'string' && query.next.startsWith('/') && !query.next.startsWith('//') ? query.next : '/';
    window.location.href = next;
  };
  return (
    <div className="min-h-screen bg-gray-50 grid place-items-center px-4">
      <form onSubmit={go} className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 w-full max-w-md space-y-4">
        <div className="flex items-center gap-2"><KeyRound className="w-5 h-5 text-indigo-600" aria-hidden /><h1 className="text-xl font-semibold text-gray-900">{S.signin.title}</h1></div>
        <p className="text-sm text-gray-600">{S.signin.lead}</p>
        <label className="block text-sm">
          <span className="text-gray-700">{S.signin.token}</span>
          <input name="token" type="password" autoComplete="off" value={tok} onChange={e => setTok(e.target.value)} className="mt-1 w-full rounded-lg border-gray-300 font-mono text-sm" />
        </label>
        {err && <ErrorBox>{err}</ErrorBox>}
        <button disabled={busy || !tok.trim()} className="w-full px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">{S.signin.go}</button>
        <p className="text-xs text-gray-500 flex gap-2"><Info className="w-4 h-4 shrink-0" aria-hidden />{S.signin.authNote}</p>
      </form>
    </div>
  );
}
