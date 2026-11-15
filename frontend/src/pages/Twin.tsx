import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { ErrorBox, Load, Notice, Page, Pill, Stat, Tabs, useAction, useLoad, fmt } from "../components/ui";

const KPIS: [string, string, string][] = [["generated_t", "Waste generated", "t"], ["collected_t", "Collected", "t"], ["recovered_material_t", "Recovered material", "t"], ["compost_estimate_t", "Compost (est.)", "t"], ["residual_t", "Residual to landfill", "t"], ["end_backlog_t", "End-of-horizon backlog", "t"], ["mrf_utilisation", "MRF utilisation", "%"], ["landfill_days_to_capacity", "Landfill days to capacity", "d"]];
export default function Twin() {
  const sc = useLoad("/simulation/scenarios");
  const [params, setParams] = useState<any>(null);
  const [name, setName] = useState("Custom scenario");
  const [res, setRes] = useState<any>(null);
  const [tab, setTab] = useState("kpi");
  const a = useAction();
  useEffect(() => { if (sc.data && !params) setParams({ ...sc.data.baseline }); }, [sc.data]);
  const run = (p: any, n: string) => a.run(async () => { const r = await api.post("/simulation/run", { name: n, params: p }); setRes(r.result); setName(n); });
  const preset = (s: any) => { const p = { ...sc.data.baseline, ...s.params }; setParams(p); run(p, s.name); };
  const changed = (k: string) => params && sc.data && params[k] !== sc.data.baseline[k];
  const diff = () => Object.fromEntries(Object.keys(params).filter(changed).map((k) => [k, params[k]]));
  const ts = res ? res.scenario.timeseries.generated.map((_: any, i: number) => ({ day: i + 1, base_backlog: res.baseline.timeseries.backlog[i], scen_backlog: res.scenario.timeseries.backlog[i], base_residual: res.baseline.timeseries.residual[i], scen_residual: res.scenario.timeseries.residual[i] })) : [];
  return (
    <Page title="Waste Digital Twin" subtitle="A simplified Python simulation of the pilot zone. Pick a scenario or move the sliders; compare against the baseline with attribution of what changed.">
      <Notice t="amber">{sc.data?.label} Results depend on documented assumptions (see “Assumptions”). Not a live operational twin; no real systems are connected.</Notice>
      {a.err && <ErrorBox error={a.err} />}
      <Load state={sc}>{(d: any) => (
        <div className="grid xl:grid-cols-3 gap-4">
          <div className="space-y-4">
            <div className="card"><h3 className="font-bold mb-2">Predefined scenarios</h3><div className="space-y-2">{d.scenarios.map((s: any) => <button key={s.id} className="w-full text-left rounded-lg border p-2.5 hover:border-forest hover:bg-mint/40 disabled:opacity-50" disabled={a.busy} onClick={() => preset(s)}><div className="font-semibold text-sm">{s.name}</div><div className="text-xs text-ink/60">{s.description}</div></button>)}</div></div>
            <div className="card"><h3 className="font-bold mb-2">Custom parameters</h3>
              <div className="space-y-3">{params && d.controls.map((c: any) => (
                <div key={c.key}><div className="flex justify-between text-xs"><label htmlFor={c.key} className="font-semibold">{c.label}</label><span className={changed(c.key) ? "text-deep font-bold" : "text-ink/60"}>{fmt(params[c.key], 2)} {c.unit !== "share" ? c.unit : ""}</span></div>
                  <input id={c.key} type="range" className="w-full accent-forest" min={c.min} max={c.max} step={c.step} value={params[c.key] ?? c.min} onChange={(e) => setParams({ ...params, [c.key]: Number(e.target.value) })} /></div>))}</div>
              <div className="flex gap-2 mt-3"><button className="btn-primary flex-1" disabled={a.busy || !params} onClick={() => run(params, "Custom scenario")}>{a.busy ? "Simulating…" : "Run scenario"}</button><button className="btn-secondary" onClick={() => setParams({ ...d.baseline })}>Reset</button></div></div>
          </div>
          <div className="xl:col-span-2 space-y-4">
            {!res && <div className="card text-sm text-ink/70">Choose a predefined scenario or adjust parameters and press <b>Run scenario</b>. You’ll see baseline vs scenario KPIs, a time series, bottlenecks, affected wards and an attribution table showing which parameter caused which change.</div>}
            {res && (<>
              <div className="card"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-bold text-lg">{name}</h2><Pill t="purple">simulated</Pill></div>
                <div className="overflow-x-auto mt-2"><table className="w-full"><thead><tr><th className="th">KPI</th><th className="th">Baseline</th><th className="th">Scenario</th><th className="th">Change</th></tr></thead><tbody>
                  {KPIS.map(([k, l, u]) => { const x = res.delta[k]; if (!x) return null; const mult = u === "%" ? 100 : 1; const bad = ["residual_t", "end_backlog_t", "collected_t_neg"].includes(k) ? x.abs > 0 : ["generated_t", "collected_t", "recovered_material_t", "compost_estimate_t", "landfill_days_to_capacity"].includes(k) ? x.abs < 0 : x.abs > 0; return <tr key={k}><td className="td font-medium">{l}</td><td className="td">{fmt(x.baseline * mult)} {u}</td><td className="td font-semibold">{fmt(x.scenario * mult)} {u}</td><td className={`td font-bold ${Math.abs(x.abs) < 0.005 ? "text-ink/40" : bad ? "text-coral" : "text-forest"}`}>{x.abs > 0 ? "+" : ""}{fmt(x.abs * mult)} ({x.pct > 0 ? "+" : ""}{fmt(x.pct)}%)</td></tr>; })}
                </tbody></table></div></div>
              <Tabs value={tab} onChange={setTab} tabs={[["kpi", "Time series"], ["attr", "Attribution"], ["neck", "Bottlenecks & wards"], ["sugg", "Suggestions"], ["assume", "Assumptions"]]} />
              {tab === "kpi" && <div className="grid md:grid-cols-2 gap-4"><div className="card"><h3 className="font-bold text-sm mb-1">Collection backlog (t)</h3><div className="h-56"><ResponsiveContainer><LineChart data={ts}><CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey="day" fontSize={10} /><YAxis fontSize={11} width={40} /><Tooltip /><Legend /><Line dataKey="base_backlog" name="Baseline" stroke="#94A3B8" dot={false} /><Line dataKey="scen_backlog" name="Scenario" stroke="#1D4ED8" dot={false} strokeWidth={2} /></LineChart></ResponsiveContainer></div></div><div className="card"><h3 className="font-bold text-sm mb-1">Residual to landfill (t/day)</h3><div className="h-56"><ResponsiveContainer><LineChart data={ts}><CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey="day" fontSize={10} /><YAxis fontSize={11} width={40} /><Tooltip /><Legend /><Line dataKey="base_residual" name="Baseline" stroke="#94A3B8" dot={false} /><Line dataKey="scen_residual" name="Scenario" stroke="#F97373" dot={false} strokeWidth={2} /></LineChart></ResponsiveContainer></div></div></div>}
              {tab === "attr" && <div className="card overflow-x-auto"><h3 className="font-bold mb-2">Which change caused what (leave-one-out)</h3><table className="w-full"><thead><tr><th className="th">Parameter changed</th><th className="th">From → To</th><th className="th">Δ residual (t)</th><th className="th">Δ recovered (t)</th><th className="th">Δ end backlog (t)</th></tr></thead><tbody>{res.attribution.map((x: any) => <tr key={x.parameter}><td className="td font-medium">{x.parameter.replace(/_/g, " ")}</td><td className="td">{String(x.from)} → {String(x.to)}</td><td className="td">{fmt(x.effect_on_residual_t)}</td><td className="td">{fmt(x.effect_on_recovered_t)}</td><td className="td">{fmt(x.effect_on_end_backlog_t)}</td></tr>)}</tbody></table></div>}
              {tab === "neck" && <div className="grid md:grid-cols-2 gap-4"><div className="card"><h3 className="font-bold mb-2">Bottlenecks</h3>{res.scenario.bottlenecks.length === 0 ? <div className="text-sm text-ink/60">None detected.</div> : res.scenario.bottlenecks.map((b: any, i: number) => <div key={i} className="text-sm py-1.5 border-b last:border-0"><Pill t={b.severity === "high" ? "red" : "amber"}>{b.stage}</Pill> {b.detail}</div>)}</div><div className="card"><h3 className="font-bold mb-2">Affected wards</h3>{res.scenario.affected_wards.length === 0 ? <div className="text-sm text-ink/60">No ward shows a capacity shortfall.</div> : res.scenario.affected_wards.map((w: any) => <div key={w.ward_id} className="text-sm py-1.5 border-b last:border-0"><b>{w.ward}</b> — short by {fmt(w.shortfall_t_per_day)} t/day (peak backlog {fmt(w.peak_backlog_t, 0)} t)</div>)}</div></div>}
              {tab === "sugg" && <div className="card"><h3 className="font-bold mb-2">Suggested mitigations <span className="text-xs font-normal text-ink/50">(rule-based, for a human to consider)</span></h3><ul className="list-disc pl-5 space-y-1 text-sm">{res.suggestions.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></div>}
              {tab === "assume" && <div className="card"><h3 className="font-bold mb-2">Model assumptions</h3><table className="w-full"><tbody>{Object.entries(res.assumptions).map(([k, v]: any) => <tr key={k}><td className="td font-medium">{v.label || k}</td><td className="td">{String(v.value)}</td><td className="td text-ink/60 text-xs">{v.basis}</td></tr>)}</tbody></table></div>}
            </>)}
          </div>
        </div>)}</Load>
    </Page>
  );
}
