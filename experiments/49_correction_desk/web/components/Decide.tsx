import React, { useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { api } from '../lib/api';
import { S } from '../lib/strings';
import { Btn, ErrorBox } from './Bits';

// A decision made outside a task, from an entity page (POST /decisions). Ownership is the API's: deciding again
// over someone else's standing decision is refused (403, naming the owner) and the page says to leave a note.
export function useDecide(onDone?: () => void) {
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');
  const [busy, setBusy] = useState(false);
  const decide = async (op: string, subject_keys: string[], payload: any = {}, note?: string) => {
    setBusy(true); setErr(''); setOk('');
    try {
      const d = await api('/decisions', { json: { op, subject_keys, payload, note: note || null, evidence: { screen: 'desk-web P2 entity page' } } });
      setOk(`Saved: ${op} · decision ${String(d.decision_id).slice(0, 8)} (yours). It reaches the pages at the next release.`);
      onDone?.();
      return d;
    } catch (e: any) { setErr(e.message); return null; } finally { setBusy(false); }
  };
  const status = <>{err && <ErrorBox>{err}{/only they or an admin|already decided/.test(err) ? ' — use “Leave a note” on that decision in History.' : ''}</ErrorBox>}
    {ok && <p className="text-sm text-green-700 flex items-center gap-1.5" role="status"><CheckCircle2 className="w-4 h-4" />{ok}</p>}</>;
  return { decide, busy, status };
}

export const WrongPanel: React.FC<{ ops: [string, string][]; children: (op: string, note: string) => React.ReactNode; title: string }> = ({ ops, children, title }) => {
  const [op, setOp] = useState('');
  const [note, setNote] = useState('');
  return (
    <div className="space-y-3" data-testid="wrong-panel">
      <div className="flex flex-wrap gap-2" role="group" aria-label={title}>
        {ops.map(([k, label]) => (
          <button key={k} onClick={() => setOp(op === k ? '' : k)} aria-pressed={op === k}
            className={`px-3 py-1 rounded-full border text-sm ${op === k ? 'bg-indigo-50 border-indigo-200 text-indigo-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}>{label}</button>))}
      </div>
      {op && <>
        {children(op, note)}
        <textarea rows={2} value={note} onChange={e => setNote(e.target.value)} dir="auto" className="w-full rounded-lg border-gray-300 text-sm" placeholder={S.work.notePh} />
      </>}
    </div>
  );
};
export { Btn };
