import { ReactNode, useEffect, useState } from "react";
import { Loader2, AlertTriangle, Inbox, X, ShieldCheck } from "lucide-react";
import { api } from "../api";

export const DATA_CLASS: Record<string, { label: string; cls: string; tip: string }> = {
  official: { label: "Official", cls: "bg-green-100 text-green-800", tip: "From an official public source" },
  pilot: { label: "Pilot", cls: "bg-blue-100 text-blue-800", tip: "Collected in a pilot" },
  estimate: { label: "Estimate", cls: "bg-amber/20 text-amber-800", tip: "Calculated with assumptions" },
  simulated: { label: "Simulated", cls: "bg-purple-100 text-purple-800", tip: "Simulated demo data — not real" },
};
export function DataBadge({ cls = "simulated" }: { cls?: string }) {
  const d = DATA_CLASS[cls] || DATA_CLASS.simulated;
  return <span title={d.tip} className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${d.cls}`}>{d.label}</span>;
}
const tone: Record<string, string> = {
  green: "bg-green-100 text-green-800", blue: "bg-blue-100 text-blue-800", amber: "bg-amber/20 text-amber-800", red: "bg-red-100 text-red-700", gray: "bg-gray-100 text-gray-700", purple: "bg-purple-100 text-purple-800",
};
export function Pill({ children, t = "gray" }: { children: ReactNode; t?: string }) {
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone[t] || tone.gray}`}>{children}</span>;
}
export function statusTone(s: string) {
  if (/complete|success|approved|closed|verified|final|resolved|received|credited|ok|recovered|transferred|available|open/.test(s)) return "green";
  if (/await|pending|requested|assigned|accepted|progress|submitted|processing|recommended|planned|live/.test(s)) return "amber";
  if (/reject|fail|escalat|cancel|flag|discrep|breach|critical|mismatch/.test(s)) return "red";
  return "gray";
}
export const StatusPill = ({ s }: { s: string }) => <Pill t={statusTone(s || "")}>{(s || "—").replace(/_/g, " ")}</Pill>;

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div className="flex items-center gap-2 py-10 justify-center text-ink/60 text-sm" role="status"><Loader2 className="animate-spin" size={18} />{label}</div>;
}
export function ErrorBox({ error, retry }: { error: any; retry?: () => void }) {
  return (
    <div className="card border-coral/40 bg-red-50 flex items-start gap-3" role="alert">
      <AlertTriangle className="text-coral shrink-0" size={20} />
      <div className="flex-1 text-sm"><div className="font-semibold">Couldn’t load this</div><div className="text-ink/70">{String(error?.message || error)}</div></div>
      {retry && <button className="btn-secondary btn-sm" onClick={retry}>Retry</button>}
    </div>
  );
}
export function Empty({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return <div className="text-center py-10 text-ink/60"><Inbox className="mx-auto mb-2 opacity-60" /><div className="font-semibold text-ink/80">{title}</div>{hint && <div className="text-sm mt-1">{hint}</div>}<div className="mt-3">{children}</div></div>;
}
export function useLoad<T = any>(path: string | null, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<any>(null);
  const [loading, setLoading] = useState(!!path);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    let alive = true;
    setLoading(true); setError(null);
    api.get(path).then((d) => alive && setData(d)).catch((e) => alive && setError(e)).finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [path, tick, ...deps]);
  return { data, error, loading, reload: () => setTick((t) => t + 1), setData };
}
export function Load<T = any>({ state, children, emptyIf }: { state: ReturnType<typeof useLoad<T>>; children: (d: T) => ReactNode; emptyIf?: (d: T) => boolean }) {
  if (state.loading && !state.data) return <Spinner />;
  if (state.error) return <ErrorBox error={state.error} retry={state.reload} />;
  if (!state.data) return null;
  if (emptyIf?.(state.data)) return <Empty title="Nothing here yet" />;
  return <>{children(state.data)}</>;
}
export function Page({ title, subtitle, actions, children, badge }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode; badge?: string }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-2xl font-extrabold text-forest flex items-center gap-2">{title}{badge && <DataBadge cls={badge} />}</h1>{subtitle && <p className="text-sm text-ink/70 mt-1 max-w-3xl">{subtitle}</p>}</div>
        <div className="flex gap-2 flex-wrap">{actions}</div>
      </div>
      {children}
    </div>
  );
}
export function Stat({ label, value, sub, tone = "forest", badge }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string; badge?: string }) {
  const c: any = { forest: "text-forest", blue: "text-deep", amber: "text-amber", coral: "text-coral" };
  return (
    <div className="card !p-4"><div className="text-xs font-semibold text-ink/60 flex items-center gap-1.5">{label}{badge && <DataBadge cls={badge} />}</div><div className={`text-2xl font-extrabold mt-1 ${c[tone]}`}>{value}</div>{sub && <div className="text-xs text-ink/60 mt-0.5">{sub}</div>}</div>
  );
}
export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => { const h = (e: KeyboardEvent) => e.key === "Escape" && onClose(); if (open) window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h); }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose} role="dialog" aria-modal="true" aria-label={title}>
      <div className={`bg-white w-full ${wide ? "sm:max-w-3xl" : "sm:max-w-lg"} max-h-[92vh] overflow-auto rounded-t-2xl sm:rounded-2xl p-5 shadow-2xl`} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3"><h2 className="font-bold text-lg text-forest">{title}</h2><button onClick={onClose} aria-label="Close" className="p-1 rounded hover:bg-gray-100"><X size={18} /></button></div>
        {children}
      </div>
    </div>
  );
}
export function Notice({ children, t = "blue", icon }: { children: ReactNode; t?: "blue" | "amber" | "green" | "red"; icon?: ReactNode }) {
  const m: any = { blue: "bg-blue-50 border-blue-200 text-blue-900", amber: "bg-amber/10 border-amber/40 text-amber-900", green: "bg-green-50 border-green-200 text-green-900", red: "bg-red-50 border-red-200 text-red-800" };
  return <div className={`rounded-lg border px-3 py-2 text-sm flex gap-2 ${m[t]}`}>{icon ?? <ShieldCheck size={16} className="mt-0.5 shrink-0" />}<div>{children}</div></div>;
}
export function Tabs({ tabs, value, onChange }: { tabs: [string, string][]; value: string; onChange: (v: string) => void }) {
  return <div className="flex gap-1 overflow-x-auto border-b border-gray-200 -mb-px" role="tablist">{tabs.map(([k, l]) => <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)} className={`px-3 py-2 text-sm font-semibold whitespace-nowrap border-b-2 ${value === k ? "border-forest text-forest" : "border-transparent text-ink/60 hover:text-ink"}`}>{l}</button>)}</div>;
}
export const fmt = (n: any, d = 1) => (n === null || n === undefined || isNaN(n) ? "—" : Number(n).toLocaleString("en-IN", { maximumFractionDigits: d }));
export const when = (s?: string) => (s ? new Date(s.endsWith("Z") ? s : s + "Z").toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>("");
  const run = async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true); setErr("");
    try { return await fn(); } catch (e: any) { setErr(e.message || String(e)); } finally { setBusy(false); }
  };
  return { busy, err, run, setErr };
}
