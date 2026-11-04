import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ChevronDown, Search, LogOut, Presentation, Check } from 'lucide-react';
import { S } from '../lib/strings';
import { useMe } from '../lib/me';
import { setShowMode, useShowMode } from '../lib/showmode';

// The top bar (regrouped for the shareholder meeting, experiment 73, 2026-11-03): one row at 1440 with every label
// visible. Story · Index ▾ · Quality ▾ · Librarian ▾ · Project ▾ · Workbench ▾ (the corrector's pages, hidden in
// presentation mode), a search box and the user menu (with the Presentation-mode switch).
type Item = { href: string; label: string; sub?: string; badge?: 'notes' };
type Group = { key: string; label: string; items: Item[]; workbench?: boolean };

const GROUPS: Group[] = [
  { key: 'index', label: 'Index', items: [
    { href: '/index-home', label: 'Overview', sub: 'The index at a glance' },
    { href: '/journals', label: 'Journals', sub: 'Every journal, the ones read whole on top' },
    { href: '/institutions', label: 'Institutions', sub: 'Universities and their countries' },
    { href: '/most-cited', label: 'Most cited', sub: 'The works the articles cite most' },
    { href: '/explore', label: 'Explorer', sub: 'Every field, sortable, exportable' },
  ] },
  { key: 'quality', label: 'Quality', items: [
    { href: '/pipeline', label: 'How a page is read', sub: 'One real page, step by step' },
    { href: '/audit', label: 'Nothing lost', sub: 'Every printed line reaches a field' },
    { href: '/how-we-collect', label: 'How we collect', sub: 'The field guide' },
  ] },
  { key: 'librarian', label: 'Librarian', items: [
    { href: '/librarian', label: 'Institutions', sub: 'The same institution written many ways' },
    { href: '/librarian/works', label: 'Cited works', sub: 'The same book cited many ways' },
  ] },
  { key: 'project', label: 'Project', items: [
    { href: '/project', label: 'The journey', sub: 'Where we are, gate by gate' },
    { href: '/plan', label: 'Plan', sub: 'What runs, what is next' },
  ] },
  { key: 'workbench', label: 'Workbench', workbench: true, items: [
    { href: '/', label: 'Task overview', sub: 'The correctors’ queue' },
    { href: '/work', label: 'Tasks', sub: 'Answer the next question' },
    { href: '/notes', label: 'Notes', sub: 'Notes on your decisions', badge: 'notes' },
    { href: '/releases', label: 'Releases', sub: 'Each published release' },
    { href: '/articles', label: 'Articles', sub: 'The article list' },
    { href: '/works', label: 'Top cited (list)', sub: 'The cited works, with ids' },
  ] },
];

function isActive(pathname: string, h: string) {
  return h === '/' ? pathname === '/' : pathname === h || pathname.startsWith(h + '/');
}

// one dropdown: opens on click, Enter, Space or ↓ (with one menu open, hovering a neighbour opens it); ↑/↓ move, Esc closes, Tab leaves
function Menu({ g, pathname, open, anyOpen, setOpen, notes }: { g: Group; pathname: string; open: boolean; anyOpen: boolean; setOpen: (k: string | null) => void; notes: number }) {
  const btn = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const viaKey = useRef(false);
  // the most specific match wins (/librarian/works must not also light /librarian)
  const best = g.items.filter(it => isActive(pathname, it.href)).sort((a, b) => b.href.length - a.href.length)[0];
  const here = !!best;
  const focusItem = (i: number) => {
    const els = list.current?.querySelectorAll<HTMLElement>('[role="menuitem"]');
    if (!els || !els.length) return;
    els[(i + els.length) % els.length].focus();
  };
  useEffect(() => { if (open && viaKey.current) setTimeout(() => focusItem(0), 0); viaKey.current = false; }, [open]);   // eslint-disable-line
  const onBtnKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') { e.preventDefault(); viaKey.current = true; setOpen(g.key); }
    if (e.key === 'Escape') setOpen(null);
  };
  const onListKey = (e: React.KeyboardEvent) => {
    const els = Array.from(list.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') || []);
    const i = els.indexOf(document.activeElement as HTMLElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); focusItem(i + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); focusItem(i - 1); }
    else if (e.key === 'Home') { e.preventDefault(); focusItem(0); }
    else if (e.key === 'End') { e.preventDefault(); focusItem(els.length - 1); }
    else if (e.key === 'Escape') { e.preventDefault(); setOpen(null); btn.current?.focus(); }
    else if (e.key === 'Tab') setOpen(null);
  };
  // with one menu open, moving the mouse onto a neighbour opens that one instead (as in a desktop menu bar)
  const enter = (e: React.PointerEvent) => { if (e.pointerType === 'mouse' && anyOpen && !open) setOpen(g.key); };
  return (
    <div className="relative" onPointerEnter={enter} data-menu={g.key}>
      <button ref={btn} type="button" aria-haspopup="menu" aria-expanded={open} aria-controls={`menu-${g.key}`}
        onClick={() => setOpen(open ? null : g.key)} onKeyDown={onBtnKey} data-testid={`nav-${g.key}`}
        className={`px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1 whitespace-nowrap transition-colors ${here ? 'bg-indigo-50 text-indigo-700' : open ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}>
        {g.label}
        <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>
      {open && (
        <div ref={list} id={`menu-${g.key}`} role="menu" aria-label={g.label} onKeyDown={onListKey}
          className="nav-drop absolute left-0 top-full mt-1.5 w-72 rounded-xl border border-gray-200 bg-white shadow-lg shadow-gray-900/5 p-1.5 z-30">
          {g.items.map(it => {
            const cur = best?.href === it.href;
            return (
              <Link key={it.href} href={it.href} role="menuitem" tabIndex={-1} aria-current={cur ? 'page' : undefined}
                onClick={() => setOpen(null)}
                className={`block rounded-lg px-3 py-2 outline-none focus-visible:outline-none focus:bg-indigo-50 hover:bg-gray-50 ${cur ? 'bg-indigo-50/70' : ''}`}>
                <span className={`flex items-center gap-2 text-sm font-medium ${cur ? 'text-indigo-700' : 'text-gray-900'}`}>
                  {it.label}
                  {it.badge === 'notes' && notes > 0 && <span className="text-[11px] bg-amber-100 text-amber-800 rounded-full px-1.5">{notes}</span>}
                </span>
                {it.sub && <span className="block text-xs text-gray-500 mt-0.5">{it.sub}</span>}
              </Link>);
          })}
        </div>)}
    </div>);
}

function UserMenu({ show }: { show: boolean }) {
  const { me } = useMe();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', h); document.addEventListener('keydown', k);
    return () => { document.removeEventListener('mousedown', h); document.removeEventListener('keydown', k); };
  }, [open]);
  const signOut = async () => { await fetch('/api/session', { method: 'DELETE' }); window.location.href = '/signin'; };
  if (!me) return null;
  const name = (me.name || me.actor_id).replace(/^\w+:/, '');
  return (
    <div className="relative ml-1" ref={box}>
      <button type="button" onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open} aria-label="Your menu" data-testid="user-menu"
        className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 grid place-items-center font-medium hover:ring-2 hover:ring-indigo-200">
        {name[0]?.toUpperCase()}
      </button>
      {open && (
        <div role="menu" className="nav-drop absolute right-0 top-full mt-1.5 w-72 rounded-xl border border-gray-200 bg-white shadow-lg shadow-gray-900/5 p-1.5 z-30">
          <div className="px-3 py-2 text-sm">
            <div className="font-medium text-gray-900">{name}</div>
            {!show && <div className="text-xs text-gray-500">{me.role}</div>}
          </div>
          <button type="button" role="menuitemcheckbox" aria-checked={show} data-testid="toggle-show"
            onClick={() => { setShowMode(!show); setOpen(false); }}
            className="w-full flex items-start gap-2.5 rounded-lg px-3 py-2 text-left hover:bg-gray-50">
            <Presentation className="w-4 h-4 mt-0.5 text-teal-600" aria-hidden />
            <span className="flex-1">
              <span className="block text-sm font-medium text-gray-900">Presentation mode</span>
              <span className="block text-xs text-gray-500">Hides ids and the workbench</span>
            </span>
            <span className={`mt-0.5 w-8 h-4.5 rounded-full relative transition-colors ${show ? 'bg-teal-500' : 'bg-gray-300'}`} style={{ height: 18 }} aria-hidden>
              <span className={`absolute top-[2px] w-3.5 h-3.5 rounded-full bg-white shadow transition-all ${show ? 'left-[16px]' : 'left-[2px]'}`} />
            </span>
          </button>
          <button type="button" role="menuitem" onClick={signOut} className="w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">
            <LogOut className="w-4 h-4 text-gray-500" aria-hidden /> {S.signin.out}
          </button>
        </div>)}
    </div>);
}

const Layout: React.FC<{ children: React.ReactNode; wide?: boolean; bare?: boolean }> = ({ children, wide, bare }) => {
  const { pathname, push, query, asPath } = useRouter();
  const { me } = useMe();
  const show = useShowMode();
  const [open, setOpen] = useState<string | null>(null);
  const [q, setQ] = useState(typeof query.q === 'string' && pathname === '/search' ? query.q : '');
  const bar = useRef<HTMLDivElement>(null);
  useEffect(() => { setOpen(null); }, [asPath]);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (bar.current && !bar.current.contains(e.target as Node)) setOpen(null); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);
  const groups = GROUPS.filter(g => !(show && g.workbench));
  const notes = me?.open_notes_on_my_decisions || 0;
  const w = wide ? 'max-w-[96rem]' : 'max-w-7xl';
  return (
    <div className="min-h-screen bg-gray-50">
      <style>{`.nav-drop{animation:nav-drop .16s cubic-bezier(.22,.7,.2,1)}@keyframes nav-drop{from{opacity:0;transform:translateY(-4px)}}`}</style>
      {!bare && (
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-20" aria-label="Desk pages">
        <div ref={bar} className={`${w} mx-auto px-4 flex items-center gap-1 h-14`}>
          <Link href={show ? '/story' : '/'} className="flex items-center gap-2 mr-3 whitespace-nowrap group" data-testid="brand">
            <span aria-hidden className="w-7 h-7 rounded-lg bg-gradient-to-br from-teal-500 to-indigo-600 grid place-items-center shadow-sm">
              <svg viewBox="0 0 20 20" className="w-4 h-4" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
                <circle cx="5" cy="14" r="2" /><circle cx="15" cy="6" r="2" /><circle cx="15" cy="15" r="1.6" />
                <path d="M6.6 12.6 13.4 7.4M6.9 14.4l6.6.5" />
              </svg>
            </span>
            <span className="font-semibold text-gray-900 group-hover:text-indigo-700 transition-colors">Mandumah Citation Index</span>
          </Link>
          <Link href="/story" aria-current={pathname === '/story' ? 'page' : undefined} data-testid="nav-story"
            className={`px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap ${pathname === '/story' ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-100'}`}>Story</Link>
          {groups.map(g => <Menu key={g.key} g={g} pathname={pathname} open={open === g.key} anyOpen={open !== null} setOpen={setOpen} notes={notes} />)}
          <form className="ml-auto flex items-center" role="search" onSubmit={e => { e.preventDefault(); if (q.trim()) push(`/search?q=${encodeURIComponent(q.trim())}`); }}>
            <label className="relative">
              <span className="sr-only">{S.search.title}</span>
              <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" aria-hidden />
              <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search the index…" dir="auto"
                className="pl-8 pr-2 py-1.5 w-48 xl:w-56 rounded-lg border-gray-300 text-sm" />
            </label>
          </form>
          {show && (
            <button type="button" onClick={() => setShowMode(false)} title="Presentation mode is on: click to turn it off" data-testid="show-chip"
              className="ml-1 inline-flex items-center gap-1 rounded-full bg-teal-50 text-teal-800 border border-teal-200 px-2.5 py-1 text-xs font-medium hover:bg-teal-100 whitespace-nowrap">
              <Check className="w-3 h-3" aria-hidden /> Presentation
            </button>)}
          <UserMenu show={show} />
        </div>
      </nav>)}
      <main className={`${w} mx-auto px-4 py-6 space-y-4`}>{children}</main>
    </div>
  );
};
export default Layout;
