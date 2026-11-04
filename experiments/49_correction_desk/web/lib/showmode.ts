// Presentation ("show") mode for shareholder meetings (experiment 73, 2026-11-03).
// On with ?show=1 (remembered in localStorage), off with ?show=0. In show mode pages hide internal ids, release
// strings, workbench menus and technical sections, and the logo leads to /story instead of the task queue.
import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';

const KEY = 'desk_show';

export function readShowMode(): boolean {
  try { return localStorage.getItem(KEY) === '1'; } catch { return false; }
}

export function setShowMode(on: boolean) {
  try { if (on) localStorage.setItem(KEY, '1'); else localStorage.removeItem(KEY); } catch { /* storage blocked */ }
  try { window.dispatchEvent(new Event('desk-show-change')); } catch { /* server render */ }
}

export function useShowMode(): boolean {
  const router = useRouter();
  const [on, setOn] = useState(false);
  useEffect(() => {
    const q = router.query.show;
    if (q === '1') setShowMode(true);
    if (q === '0') setShowMode(false);
    setOn(readShowMode());
    const h = () => setOn(readShowMode());
    window.addEventListener('desk-show-change', h);
    return () => window.removeEventListener('desk-show-change', h);
  }, [router.query.show]);
  return on;
}
