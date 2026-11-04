import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from './api';

export type Me = {
  actor_id: string; name: string; role: 'corrector' | 'admin'; skills: string[]; ui_lang: string;
  decisions: Record<string, number>; decisions_last_24h: number; open_notes_on_my_decisions: number; holding_tasks: number[];
};
const Ctx = createContext<{ me: Me | null; reload: () => void }>({ me: null, reload: () => {} });

export const MeProvider: React.FC<{ children: React.ReactNode; skip?: boolean }> = ({ children, skip }) => {
  const [me, setMe] = useState<Me | null>(null);
  const reload = () => { if (!skip) api<Me>('/me').then(setMe).catch(() => setMe(null)); };
  useEffect(reload, [skip]);
  return <Ctx.Provider value={{ me, reload }}>{children}</Ctx.Provider>;
};
export const useMe = () => useContext(Ctx);

// who may do what to a decision (DESIGN §7): its owner changes it, an admin fixes it, anyone else leaves a note
export function rightsOn(me: Me | null, d: { actor_id: string }): 'owner' | 'admin' | 'other' {
  if (!me) return 'other';
  if (d.actor_id === me.actor_id) return 'owner';
  if (me.role === 'admin') return 'admin';
  return 'other';
}

export function useApi<T = any>(path: string | null, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const load = () => {
    if (!path) return;
    setLoading(true); setErr('');
    api<T>(path).then(d => setData(d)).catch(e => setErr(String(e.message || e))).finally(() => setLoading(false));
  };
  useEffect(load, [path, ...deps]);
  return { data, err, loading, reload: load, setData };
}
