import { ReactNode, useEffect, useState } from "react";
import { Loader2, AlertTriangle, Inbox, X, ShieldCheck } from "lucide-react";
import { api } from "../api";

export const DATA_CLASS: Record<string, { label: string; cls: string; tip: string }> = {
  official: { label: "Official", cls: "bg-[#E6F4EA] text-[#1E7B34]", tip: "From an official public source" },
  pilot: { label: "Pilot", cls: "bg-mint text-forest", tip: "Collected in a pilot" },
  estimate: { label: "Estimate", cls: "bg-[#FEF5E0] text-[#8A5A00]", tip: "Calculated with assumptions" },
  simulated: { label: "Simulated", cls: "bg-[#F0EBFF] text-[#5B3FC4]", tip: "Simulated demo data — not real" },
};
export function DataBadge({ cls = "simulated" }: { cls?: string }) {
  // "Simulated" is already stated once in the top bar; repeating it on every number is noise.
  if (!cls || cls === "simulated") return null;
  const d = DATA_CLASS[cls] || DATA_CLASS.simulated;
  return <span title={d.tip} className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold ${d.cls}`}>{d.label}</span>;
}
const tone: Record<string, string> = {
  green: "bg-[#E6F4EA] text-[#1E7B34]", blue: "bg-mint text-forest", amber: "bg-[#FEF5E0] text-[#8A5A00]", red: "bg-[#FDE7EA] text-[#C4122F]", gray: "bg-btn text-ink/70", purple: "bg-[#F0EBFF] text-[#5B3FC4]",
};
export function Pill({ children, t = "gray" }: { children: ReactNode; t?: string }) {
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-[12px] font-semibold capitalize ${tone[t] || tone.gray}`}>{children}</span>;
}
export function statusTone(s: string) {
  if (/complete|success|approved|closed|verified|final|resolved|received|credited|ok|recovered|transferred|available|open/.test(s)) return "green";
  if (/await|pending|requested|assigned|accepted|progress|submitted|processing|recommended|planned|live/.test(s)) return "amber";
  if (/reject|fail|escalat|cancel|flag|discrep|breach|critical|mismatch/.test(s)) return "red";
  return "gray";
}
export const StatusPill = ({ s }: { s: string }) => <Pill t={statusTone(s || "")}>{(s || "—").replace(/_/g, " ")}</Pill>;

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div className="flex items-center gap-2 py-10 justify-center text-ink/60 text-[15px]" role="status"><Loader2 className="animate-spin text-forest" size={20} />{label}</div>;
}
export function ErrorBox({ error, retry }: { error: any; retry?: () => void }) {
  return (
    <div className="card flex items-start gap-3 border-l-4 border-coral" role="alert">
      <AlertTriangle className="text-coral shrink-0" size={20} />
      <div className="flex-1 text-sm"><div className="font-semibold">Couldn’t load this</div><div className="text-ink/70">{String(error?.message || error)}</div></div>
      {retry && <button className="btn-secondary btn-sm" onClick={retry}>Retry</button>}
    </div>
  );
}
export function Empty({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return <div className="text-center py-10 text-ink/60"><span className="mx-auto mb-3 grid place-items-center h-14 w-14 rounded-full bg-cream"><Inbox className="opacity-60" /></span><div className="font-semibold text-ink text-[17px]">{title}</div>{hint && <div className="text-sm mt-1">{hint}</div>}<div className="mt-3">{children}</div></div>;
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
      <div className="flex flex-wrap items-end justify-between gap-3 pb-1">
        <div><h1 className="text-[26px] leading-tight font-bold text-ink flex items-center gap-2">{title}{badge && <DataBadge cls={badge} />}</h1>{subtitle && <p className="text-[15px] text-ink/60 mt-1 max-w-3xl">{subtitle}</p>}</div>
        <div className="flex gap-2 flex-wrap">{actions}</div>
      </div>
      {children}
    </div>
  );
}
export function Stat({ label, value, sub, badge }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string; badge?: string }) {
    return (
    <div className="card !p-4"><div className="text-[13px] font-semibold text-ink/60 flex items-center gap-1.5">{label}{badge && <DataBadge cls={badge} />}</div><div className="text-[26px] leading-tight font-bold mt-1 text-ink">{value}</div>{sub && <div className="text-[13px] text-ink/60 mt-0.5">{sub}</div>}</div>
  );
}
export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => { const h = (e: KeyboardEvent) => e.key === "Escape" && onClose(); if (open) window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h); }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-white/70 backdrop-blur-[2px] flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose} role="dialog" aria-modal="true" aria-label={title}>
      <div className={`bg-white w-full ${wide ? "sm:max-w-3xl" : "sm:max-w-lg"} max-h-[92vh] overflow-auto rounded-t-xl sm:rounded-lg shadow-pop`} onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-white z-10 flex items-center justify-center h-[60px] border-b border-line/70 px-14"><h2 className="font-bold text-[20px] text-ink truncate">{title}</h2><button onClick={onClose} aria-label="Close" className="icon-btn absolute right-4 !h-9 !w-9"><X size={20} /></button></div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
export function Notice({ children, t = "blue", icon }: { children: ReactNode; t?: "blue" | "amber" | "green" | "red"; icon?: ReactNode }) {
  const m: any = { blue: "bg-mint text-ink [&>svg]:text-forest", amber: "bg-[#FEF5E0] text-ink [&>svg]:text-[#B07800]", green: "bg-[#E6F4EA] text-ink [&>svg]:text-fresh", red: "bg-[#FDE7EA] text-ink [&>svg]:text-coral" };
  return <div className={`rounded-lg px-3 py-2.5 text-[14px] flex gap-2 ${m[t]}`}>{icon ?? <ShieldCheck size={16} className="mt-0.5 shrink-0" />}<div>{children}</div></div>;
}
export function Tabs({ tabs, value, onChange }: { tabs: [string, string][]; value: string; onChange: (v: string) => void }) {
  return <div className="flex gap-1 overflow-x-auto border-b border-line/70" role="tablist">{tabs.map(([k, l]) => <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)} className={`relative px-4 h-12 text-[15px] font-semibold whitespace-nowrap ${value === k ? "text-forest" : "text-ink/60 rounded-md my-1 !h-10 hover:bg-hover"}`}>{l}{value === k && <span className="absolute left-0 right-0 bottom-0 h-[3px] rounded-t bg-forest" />}</button>)}</div>;
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
