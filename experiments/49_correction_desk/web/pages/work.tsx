import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Clock, CheckCircle2, ExternalLink } from 'lucide-react';
import Layout from '../components/Layout';
import { Btn, Card, Chip, Crop, Empty, ErrorBox, Kbd, T, n } from '../components/Bits';
import { GroupsSummary, Member, SplitPicker, booksOf } from '../components/SplitPicker';
import { api, cropOfAnchor, hrefOf, isArabic } from '../lib/api';
import { useMe } from '../lib/me';
import { S, f, kindLabel } from '../lib/strings';

type Task = any;
type Answer = (op: string, keys?: string[] | null, payload?: any, crops?: (string | null)[]) => Promise<any>;
type Keys = React.MutableRefObject<Record<string, () => void>>;
const KINDS = ['work_joined_without_author', 'possible_same_work', 'byline_twin'];

function useLease(until?: string) {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    if (!until) { setLeft(null); return; }
    const tick = () => setLeft(Math.max(0, Math.round((Date.parse(until) - Date.now()) / 1000)));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [until]);
  return left;
}

// ------------------------------------------------------------------ 1. a card joined without an author
const JoinedWithoutAuthor: React.FC<{ task: Task; answer: Answer; busy: boolean; keys: Keys; note: React.ReactNode }> = ({ task, answer, busy, keys, note }) => {
  const card = task.subject_keys[0];
  const id = card.split(':')[1];
  const members: Member[] = useMemo(() => (task.candidates || []).flatMap((g: any) => g.members.map((m: any) => ({
    key: m.mention, stem: m.stem, printed: m.printed, anchor: m.anchor, authors: m.authors || [],
  }))), [task]);
  const init = useMemo(() => {
    const g: Record<string, number> = {};
    let b = 0;
    (task.candidates || []).forEach((grp: any) => {
      const authorless = !grp.members.some((m: any) => (m.authors || []).length);
      if (!authorless) b += 1;
      grp.members.forEach((m: any) => { g[m.mention] = authorless ? 0 : b; });
    });
    return g;
  }, [task]);
  const [group, setGroup] = useState(init);
  useEffect(() => setGroup(init), [init]);
  const [w, setW] = useState<any>(null);
  useEffect(() => { api(`/works/${id}`).then(setW).catch(() => setW(null)); }, [id]);
  const { books, unclear, labels } = booksOf(members, group);
  const title = w?.title || (task.question || '').match(/«(.+?)»/)?.[1] || id;
  const crops = members.map(m => cropOfAnchor(m.anchor));
  const split = () => books.length >= 2 && answer('split_work', null, { groups: books.map((b, i) => ({ members: b, label: labels[i] || null })) }, crops);
  const one = () => answer('confirm_work', null, {}, crops);
  keys.current = { Enter: split, a: one };
  return (
    <>
      <Head kind={task.kind} task={task} title={S.work.wjQ}
        lead={<>{f(S.work.wjLead, { n: members.length, title })} {w && <>Cited by {n(w.n_citing_pubs)} articles ({n(w.n_mentions)} mentions).</>}</>} />
      <div className="grid lg:grid-cols-3 gap-4">
        <Card pad={false} className="lg:col-span-2" title={S.work.citations} right={<span className="text-xs text-gray-500">{S.work.pick} · <Kbd>0</Kbd>–<Kbd>9</Kbd> on a row</span>}>
          <SplitPicker members={members} group={group} setGroup={setGroup} />
        </Card>
        <aside className="space-y-4">
          <Card title="Your answer">
            <div className="space-y-3">
              <GroupsSummary members={members} group={group} />
              {unclear.length > 0 && books.length >= 2 && <p className="text-xs text-amber-800">{f(S.work.unclearStay, { id })}</p>}
              {note}
              <div className="grid grid-cols-2 gap-2">
                <Btn kind="primary" disabled={busy || books.length < 2} onClick={split} data-testid="save-split">{S.work.saveSplit} <Kbd dark>↵</Kbd></Btn>
                <Btn disabled={busy} onClick={one} data-testid="all-one">{S.work.allOne} <Kbd>a</Kbd></Btn>
              </div>
            </div>
          </Card>
          <Does>
            <p>{books.length >= 2 ? f(S.work.wjDoesSplit, { id, books: books.length }) : f(S.work.wjDoesOne, { id })}</p>
            <p>{S.work.ownNote}</p>
            <p className="text-xs"><Link className="text-indigo-700 hover:underline" href={hrefOf(card)!}>Work page {id}</Link></p>
          </Does>
        </aside>
      </div>
    </>
  );
};

// ------------------------------------------------------------------ 2. one work on two cards?
const SameWork: React.FC<{ task: Task; answer: Answer; busy: boolean; keys: Keys; note: React.ReactNode }> = ({ task, answer, busy, keys, note }) => {
  const [a, b] = task.candidates;
  const [keep, other] = (a.n_mentions >= b.n_mentions ? [a, b] : [b, a]);
  const crops = [...a.sample, ...b.sample].map((m: any) => cropOfAnchor(m.anchor));
  const same = () => answer('same_work', [keep.work, other.work], {}, crops);
  const not = () => answer('not_same_work', [a.work, b.work], {}, crops);
  keys.current = { '1': same, '2': not };
  const g = task.machine_guess || {};
  const side = (s: any, label: string) => (
    <Card key={s.work} title={<span className="flex items-center gap-2"><span className="w-7 h-7 rounded-lg bg-gray-100 text-gray-700 grid place-items-center text-sm">{label}</span><T text={s.title} className="text-lg" /></span>}
      right={<Link href={hrefOf(s.work)!} className="text-xs text-indigo-700 hover:underline flex items-center gap-1">{s.work.split(':')[1]} <ExternalLink className="w-3 h-3" /></Link>}>
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2 text-xs text-gray-600">
          <Chip>{f(S.work.mentions, { n: s.n_mentions })}</Chip><Chip>{f(S.work.articlesN, { n: s.n_articles })}</Chip>
          {s.authors?.map((x: string) => <Chip key={x} tone="indigo"><span className="ar-inline">{x}</span></Chip>)}
        </div>
        <p className="text-xs font-medium text-gray-500">{S.work.sample}</p>
        <ul className="space-y-3">{s.sample.map((m: any) => (
          <li key={m.mention} className="space-y-1">
            <Crop src={cropOfAnchor(m.anchor)} maxH="max-h-24" rtl={isArabic(m.printed)} />
            <T as="p" text={m.printed} className="text-[15px] leading-7" />
            <p className="text-xs text-gray-500"><Link href={`/articles/${encodeURIComponent(m.stem)}`} className="hover:underline">{m.stem}</Link></p>
          </li>))}
        </ul>
      </div>
    </Card>
  );
  return (
    <>
      <Head kind={task.kind} task={task} title={S.work.swQ} lead={f(S.work.swLead, { rule: task.source?.rule?.replace('probe B under-merge: ', '') || '' })} />
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 grid md:grid-cols-2 gap-4">{side(a, 'A')}{side(b, 'B')}</div>
        <aside className="space-y-4">
          <Card title="Your answer">
            <div className="space-y-3">
              {g.op && <p className="text-xs text-gray-500">{f(S.work.machine, { g: g.op === 'same_work' ? S.work.same : S.work.notSame, p: Math.round((g.p_same || 0) * 100) })}</p>}
              {note}
              <div className="grid grid-cols-2 gap-2">
                <Btn kind="primary" disabled={busy} onClick={same} data-testid="same">{S.work.same} <Kbd dark>1</Kbd></Btn>
                <Btn disabled={busy} onClick={not} data-testid="not-same">{S.work.notSame} <Kbd>2</Kbd></Btn>
              </div>
            </div>
          </Card>
          <Does>
            <p>{f(S.work.swDoesSame, { keep: keep.work.split(':')[1], other: other.work.split(':')[1] })}</p>
            <p>{S.work.swDoesNot}</p>
            <p>{S.work.ownNote}</p>
          </Does>
        </aside>
      </div>
    </>
  );
};

// ------------------------------------------------------------------ 3. a byline counted twice?
const BylineTwin: React.FC<{ task: Task; answer: Answer; busy: boolean; keys: Keys; note: React.ReactNode }> = ({ task, answer, busy, keys, note }) => {
  const prov = task.subject_keys[0];
  const cands = task.candidates || [];
  const guessIdx = Math.max(0, cands.findIndex((c: any) => task.machine_guess?.subject_keys?.[0] === c.person));
  const [pick, setPick] = useState(task.machine_guess ? guessIdx : 0);
  const [p, setP] = useState<any>(null);
  useEffect(() => { setPick(task.machine_guess ? guessIdx : 0); api(`/persons/${prov.split(':')[1]}`).then(setP).catch(() => setP(null)); }, [task.task_id]);
  const stem = task.source?.stem;
  const bylines = (p?.works || []).flatMap((w: any) => w.bylines).filter((b: any) => !stem || (b.key || '').includes(stem));
  const crops = bylines.map((b: any) => cropOfAnchor(b.anchor));
  const same = () => answer('same_person', [cands[pick].person, prov], {}, crops);
  const none = async () => {
    const d = await answer('not_same_person', [cands[0].person, prov], {}, crops);
    if (d) for (const c of cands.slice(1)) await api('/decisions', { json: { op: 'not_same_person', subject_keys: [c.person, prov], note: `with task ${task.task_id}: none of the contributors` } }).catch(() => null);
  };
  const ks: Record<string, () => void> = { Enter: same, n: none };
  cands.slice(0, 9).forEach((_: any, i: number) => { ks[String(i + 1)] = () => setPick(i); });
  keys.current = ks;
  return (
    <>
      <Head kind={task.kind} task={task} title={S.work.btQ} lead={f(S.work.btLead, { name: task.source?.byline, stem })} />
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Card title={S.work.theByline} right={stem && <Link href={`/articles/${encodeURIComponent(stem)}`} className="text-xs text-indigo-700 hover:underline">{stem}</Link>}>
            <div className="space-y-2">
              {bylines.length ? bylines.map((b: any) => (
                <div key={b.key} className="space-y-1"><Crop src={cropOfAnchor(b.anchor)} maxH="max-h-24" rtl={isArabic(b.printed)} /><T as="p" text={b.printed} className="text-lg" /></div>
              )) : <T as="p" text={task.source?.byline} className="text-lg" />}
            </div>
          </Card>
          <Card pad={false} title={S.work.candidates} right={<span className="text-xs text-gray-500"><Kbd>1</Kbd>–<Kbd>9</Kbd> pick</span>}>
            <ul className="divide-y divide-gray-100" data-testid="candidates">{cands.map((c: any, i: number) => (
              <li key={c.person}>
                <label className={`px-5 py-3 flex items-start gap-3 cursor-pointer ${pick === i ? 'bg-indigo-50/60' : 'hover:bg-gray-50'}`}>
                  <input type="radio" name="cand" checked={pick === i} onChange={() => setPick(i)} className="mt-1.5 text-indigo-600" />
                  <span className="w-7 h-7 rounded-lg bg-gray-100 text-gray-700 grid place-items-center text-sm font-medium shrink-0">{i + 1}</span>
                  <span className="min-w-0 space-y-0.5">
                    <T as="p" text={c.heading} className="text-lg text-gray-900" />
                    {c.latin && <p className="text-sm text-gray-700">{c.latin}</p>}
                    <p className="text-xs text-gray-500 flex flex-wrap gap-2">
                      <Link href={hrefOf(c.person)!} className="font-mono hover:underline" onClick={e => e.stopPropagation()}>{c.person.split(':')[1]}</Link>
                      <span>{c.role}</span>{c.authority && <span>{f(S.work.authority, { a: c.authority })}</span>}
                      <span>{f(S.work.works, { n: c.n_works })}</span><Chip tone={c.score >= 0.5 ? 'green' : 'gray'}>{f(S.work.score, { s: c.score })}</Chip>
                    </p>
                  </span>
                </label>
              </li>))}
            </ul>
          </Card>
        </div>
        <aside className="space-y-4">
          <Card title="Your answer">
            <div className="space-y-3">
              {note}
              <div className="grid grid-cols-2 gap-2">
                <Btn kind="primary" disabled={busy || !cands.length} onClick={same} data-testid="same-person">{S.work.samePerson} <Kbd dark>↵</Kbd></Btn>
                <Btn disabled={busy || !cands.length} onClick={none} data-testid="none">{S.work.noneOfThem} <Kbd>n</Kbd></Btn>
              </div>
            </div>
          </Card>
          <Does>
            <p>{f(S.work.btDoesSame, { cand: cands[pick]?.heading || '' })}</p>
            <p>{S.work.btDoesNone}</p>
            <p>{S.work.ownNote}</p>
          </Does>
        </aside>
      </div>
    </>
  );
};

const Generic: React.FC<{ task: Task }> = ({ task }) => (
  <>
    <Head kind={task.kind} task={task} title={task.question || kindLabel(task.kind)} lead={S.work.generic} />
    <Card title="Task"><pre className="text-xs overflow-x-auto">{JSON.stringify(task.candidates, null, 1)}</pre></Card>
  </>
);

const Head: React.FC<{ kind: string; task: Task; title: string; lead: React.ReactNode }> = ({ kind, task, title, lead }) => (
  <div>
    <p className="text-xs font-medium text-indigo-700 uppercase tracking-wide">{kindLabel(kind)} · {f(S.work.taskOf, { id: task.task_id })} · priority {Number(task.priority).toFixed(1)}</p>
    <h1 className="text-xl font-semibold text-gray-900 mt-1" data-testid="task-title">{title}</h1>
    <p className="text-sm text-gray-500 mt-1">{lead}</p>
  </div>
);

const Does: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Card title={S.work.whatDoes}><div className="text-sm text-gray-600 space-y-2">{children}</div></Card>
);

// ------------------------------------------------------------------ the screen: one task at a time
export default function Work() {
  const router = useRouter();
  const { reload: reloadMe } = useMe();
  const kind = typeof router.query.kind === 'string' ? router.query.kind : '';
  const [task, setTask] = useState<Task | null | undefined>(undefined);
  const [err, setErr] = useState('');
  const [saved, setSaved] = useState('');
  const [busy, setBusy] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [count, setCount] = useState(0);
  const keys = useRef<Record<string, () => void>>({});
  const left = useLease(task?.lease_until);

  const next = useCallback(async () => {
    setErr(''); setSaved(''); setNoteText(''); keys.current = {};
    try { setTask(await api(`/queue/next${kind ? `?kind=${kind}` : ''}`)); } catch (e: any) { setErr(e.message); setTask(null); }
  }, [kind]);
  useEffect(() => { if (router.isReady) next(); }, [router.isReady, kind]);

  const answer: Answer = async (op, subject_keys, payload, crops) => {
    if (!task || busy) return null;
    setBusy(true); setErr('');
    try {
      const d = await api(`/tasks/${task.task_id}/answer`, { json: {
        op, subject_keys: subject_keys || undefined, payload: payload || {}, note: noteText || null, confidence: 'sure',
        evidence: { screen: 'desk-web P2 Work', crops: (crops || []).filter(Boolean) },
      } });
      setSaved(S.work.saved); setCount(c => c + 1); reloadMe();
      setTimeout(next, 700);
      return d;
    } catch (e: any) { setErr(e.message); return null; } finally { setBusy(false); }
  };
  const pass = async (how: 'skip' | 'unsure') => {
    if (!task || busy) return;
    setBusy(true);
    try { await api(`/tasks/${task.task_id}/${how}`, { json: { note: noteText || null } }); await next(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || e.metaKey || e.ctrlKey || e.altKey) return;
      const all: Record<string, () => void> = { ...keys.current, u: () => pass('unsure'), s: () => pass('skip') };
      const fn = all[e.key];
      if (fn) { e.preventDefault(); fn(); }
    };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  });

  const note = (
    <div>
      <label htmlFor="note" className="block text-xs text-gray-500 mb-1">{S.work.note}</label>
      <textarea id="note" rows={2} value={noteText} onChange={e => setNoteText(e.target.value)} dir="auto" placeholder={S.work.notePh} className="w-full rounded-lg border-gray-300 text-sm" />
      <div className="grid grid-cols-2 gap-2 mt-2">
        <Btn disabled={busy} onClick={() => pass('unsure')} data-testid="unsure">{S.work.unsure} <Kbd>u</Kbd></Btn>
        <Btn disabled={busy} onClick={() => pass('skip')} data-testid="skip">{S.work.skip} <Kbd>s</Kbd></Btn>
      </div>
      {saved && <p className="text-sm text-green-700 flex items-center gap-1.5 mt-2" role="status" data-testid="saved"><CheckCircle2 className="w-4 h-4" />{saved}</p>}
      {err && <div className="mt-2"><ErrorBox>{err}</ErrorBox></div>}
    </div>
  );
  const props = task ? { task, answer, busy, keys, note } : null;
  return (
    <Layout>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2 text-sm" role="group" aria-label="Task kind">
          {[['', S.work.all], ...KINDS.map(k => [k, kindLabel(k)])].map(([k, label]) => (
            <button key={k} onClick={() => router.push(k ? `/work?kind=${k}` : '/work')} aria-pressed={kind === k}
              className={`px-3 py-1 rounded-full border ${kind === k ? 'bg-indigo-50 border-indigo-200 text-indigo-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}>{label}</button>))}
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          {count > 0 && <span>{f(S.work.sessionDone, { n: count })}</span>}
          {task && left != null && <span className="flex items-center gap-1"><Clock className="w-4 h-4" />{left > 0 ? f(S.work.leaseLeft, { t: `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}` }) : S.work.leaseGone}</span>}
        </div>
      </div>
      {task === undefined && <Empty>{S.common.loading}</Empty>}
      {task === null && <>{err && <ErrorBox>{err}</ErrorBox>}<Empty>{S.work.none}</Empty></>}
      {props && (
        <div key={task.task_id} data-testid="task" data-kind={task.kind} data-task={task.task_id} className="space-y-4">
          {task.kind === 'work_joined_without_author' ? <JoinedWithoutAuthor {...props} />
            : task.kind === 'possible_same_work' ? <SameWork {...props} />
              : task.kind === 'byline_twin' ? <BylineTwin {...props} />
                : <><Generic task={task} /><Card>{note}</Card></>}
        </div>
      )}
    </Layout>
  );
}
