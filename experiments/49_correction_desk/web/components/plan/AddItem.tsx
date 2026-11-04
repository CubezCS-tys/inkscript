import React, { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { api } from '../../lib/api';
import { PlanData } from './model';

// "Add item" (admins only; pages/plan.tsx): one form for a piece of work, something only the owner can do, or a
// promise. It posts to /desk/api/plan/items, which writes through desk/plan_cli.py (the same code the shell uses) and
// logs the admin's id and the time in the plan's log.

type Kind = 'work' | 'needs_you' | 'promise';
const AddItem: React.FC<{ d: PlanData; onDone: () => void }> = ({ d, onDone }) => {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<Kind>('work');
  const [f, setF] = useState<Record<string, string>>({ lane: 'extraction', status: 'planned' });
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const words = (f.title || '').trim().split(/\s+/).filter(Boolean).length;
  const toIso = (v?: string) => (v ? new Date(v).toISOString() : undefined);   // datetime-local is the viewer's own clock
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true);
    try {
      await api('/plan/items', { json: {
        kind, title: f.title, desc: f.desc || undefined, lane: kind === 'work' ? f.lane : undefined,
        status: kind === 'work' ? f.status : undefined, planned_start: kind === 'work' ? toIso(f.ps) : undefined,
        planned_end: kind === 'work' ? toIso(f.pe) : undefined, due: kind !== 'work' ? toIso(f.due) : undefined,
        urgency: kind === 'needs_you' ? f.urgency || undefined : undefined,
        link_label: f.href ? 'Open' : undefined, link_href: f.href || undefined,
      } });
      setOpen(false); setF({ lane: 'extraction', status: 'planned' }); onDone();
    } catch (x: any) { setErr(String(x.message || x)); } finally { setBusy(false); }
  };
  if (!open) return <button onClick={() => setOpen(true)} data-testid="plan-add" className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"><Plus className="w-4 h-4" />Add item</button>;
  const inp = 'w-full rounded-lg border-gray-300 text-sm';
  return (
    <div className="fixed inset-0 z-50 bg-black/20 flex items-end md:items-center justify-center p-0 md:p-4" onClick={() => setOpen(false)}>
      <form onSubmit={submit} onClick={e => e.stopPropagation()} className="bg-white w-full md:w-[460px] rounded-t-2xl md:rounded-2xl shadow-xl p-4 space-y-3" data-testid="plan-add-form">
        <div className="flex items-center"><h2 className="font-semibold flex-1">Add to the plan</h2><button type="button" onClick={() => setOpen(false)} aria-label="Close" className="p-1 rounded hover:bg-gray-100"><X className="w-4 h-4" /></button></div>
        <div className="flex rounded-xl border border-gray-200 p-1 text-sm">
          {([['work', 'Work'], ['needs_you', 'Needs the owner'], ['promise', 'Promise']] as const).map(([k, l]) => (
            <button type="button" key={k} onClick={() => setKind(k)} className={`flex-1 rounded-lg py-1 ${kind === k ? 'bg-indigo-600 text-white' : 'text-gray-600'}`}>{l}</button>))}
        </div>
        <label className="block text-sm">Title <span className={`text-xs ${words > 6 ? 'text-red-600' : 'text-gray-400'}`}>({words}/6 words)</span>
          <input className={inp} value={f.title || ''} onChange={set('title')} required maxLength={40} /></label>
        <label className="block text-sm">{kind === 'needs_you' ? 'The question' : 'One line: what it is'}<textarea className={inp} rows={2} value={f.desc || ''} onChange={set('desc')} /></label>
        {kind === 'work' && <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm">Lane<select className={inp} value={f.lane} onChange={set('lane')}>
            {d.plan.lanes.filter(l => l.key !== 'needs_you').map(l => <option key={l.key} value={l.key}>{l.label}</option>)}</select></label>
          <label className="block text-sm">Status<select className={inp} value={f.status} onChange={set('status')}><option value="planned">Planned</option><option value="running">Running now</option></select></label>
          {f.status === 'planned' && <><label className="block text-sm">Planned start<input type="datetime-local" className={inp} value={f.ps || ''} onChange={set('ps')} /></label>
            <label className="block text-sm">Planned end<input type="datetime-local" className={inp} value={f.pe || ''} onChange={set('pe')} /></label></>}
        </div>}
        {kind !== 'work' && <label className="block text-sm">Due (optional, your clock)<input type="datetime-local" className={inp} value={f.due || ''} onChange={set('due')} /></label>}
        {kind === 'needs_you' && <label className="block text-sm">Urgency<input className={inp} value={f.urgency || ''} onChange={set('urgency')} placeholder="soon, this week, any time…" /></label>}
        {kind !== 'promise' && <label className="block text-sm">Desk link (optional)<input className={inp} value={f.href || ''} onChange={set('href')} placeholder="/audit" /></label>}
        {err && <p className="text-sm text-red-700">{err}</p>}
        <p className="text-[11px] text-gray-500">Saved through the plan's own tool, with your name and the time in its log.</p>
        <button disabled={busy || words > 6} className="w-full rounded-xl bg-indigo-600 text-white py-2 text-sm font-medium disabled:opacity-50">{busy ? 'Saving…' : 'Add'}</button>
      </form>
    </div>);
};
export default AddItem;
