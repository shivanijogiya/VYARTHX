import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, setToken, getToken } from "./api";

type Ctx = { user: any; meta: any; loading: boolean; login: (e: string, p: string) => Promise<void>; logout: () => void; refresh: () => Promise<void>; setSession: (t: string, u: any) => void };
const C = createContext<Ctx>(null as any);
export const useAuth = () => useContext(C);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<any>(null);
  const [meta, setMeta] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const refresh = async () => {
    if (!getToken()) { setUser(null); return; }
    try { setUser(await api.get("/auth/me")); } catch { setUser(null); }
  };
  useEffect(() => {
    (async () => {
      try { setMeta(await api.get("/meta")); } catch { /* backend down handled in UI */ }
      await refresh();
      setLoading(false);
    })();
  }, []);
  const login = async (email: string, password: string) => {
    const r = await api.post("/auth/login", { email, password });
    setToken(r.token); setUser(r.user);
  };
  const setSession = (t: string, u: any) => { setToken(t); setUser(u); };
  const logout = () => { setToken(null); setUser(null); location.href = "/login"; };
  return <C.Provider value={{ user, meta, loading, login, logout, refresh, setSession }}>{children}</C.Provider>;
}
