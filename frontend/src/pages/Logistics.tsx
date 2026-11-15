import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import MapView from "../components/MapView";
import { DataBadge, Empty, ErrorBox, Load, Notice, Page, Pill, Stat, StatusPill, Tabs, useAction, useLoad, fmt } from "../components/ui";

const COLORS = ["#1D4ED8", "#166534", "#F59E0B", "#F97373", "#38BDF8", "#7C3AED", "#0F766E", "#B45309"];
export default function Logistics() {
  const dem = useLoad("/logistics/demand");
  const al = useLoad("/logistics/alerts");
  const veh = useLoad("/vehicles");
  const routes = useLoad("/logistics/routes");
  const [plan, setPlan] = useState<any>(null);
  const [unavail, setUnavail] = useState<number[]>([]);
  const [tab, setTab] = useState("plan");
  const a = useAction();
  const run = () => a.run(async () => { const r = await api.post("/logistics/plan", { unavailable_vehicle_ids: unavail }); setPlan(r); routes.reload(); });
  const decide = (ok: boolean) => a.run(async () => { await api.post(`/approvals/${plan.approval_id}/decide`, { approve: ok, note: ok ? "Dispatch approved (simulation)" : "Rejected" }); setPlan({ ...plan, approval_id: null, decided: ok ? "approved" : "rejected" }); routes.reload(); veh.reload(); });
  const p = plan?.plan;
  return (
    <Page title="Dynamic Collection" subtitle="Forecast-driven demand, vehicle capacity and priority-aware routing with OR-Tools. Plans are proposals: a human must approve — and no real vehicle is dispatched in this build.">
      {a.err && <ErrorBox error={a.err} />}
      <Tabs value={tab} onChange={setTab} tabs={[["plan", "Plan routes"], ["demand", "Demand & capacity"], ["fleet", "Fleet"], ["history", "Plans"]]} />
      {tab === "plan" && (<>
        <div className="card flex flex-wrap items-end gap-3"><div><div className="label">Mark vehicles unavailable (what-if)</div><div className="flex flex-wrap gap-1 max-w-xl">{veh.data?.slice(0, 14).map((v: any) => <label key={v.id} className={`text-xs border rounded-full px-2 py-1 cursor-pointer ${unavail.includes(v.id) ? "bg-coral text-white" : "bg-white"}`}><input type="checkbox" className="hidden" checked={unavail.includes(v.id)} onChange={() => setUnavail((u) => (u.includes(v.id) ? u.filter((x) => x !== v.id) : [...u, v.id]))} />{v.code}</label>)}</div></div><button className="btn-primary" onClick={run} disabled={a.busy}>{a.busy ? "Optimising…" : "Generate route plan"}</button></div>
        {p && (<>
          <Notice t={plan.decided ? "green" : "amber"}>{plan.decided ? `Plan ${plan.decided} (simulation only — no vehicle dispatched).` : plan.summary}</Notice>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3"><Stat label="Routes" value={p.routes.length} /><Stat label="Total distance" value={`${fmt(p.routes.reduce((s: number, r: any) => s + r.distance_km, 0))} km`} tone="blue" /><Stat label="Total load" value={`${fmt(p.routes.reduce((s: number, r: any) => s + r.load_kg, 0), 0)} kg`} tone="amber" /><Stat label="Unserved stops" value={p.unserved?.length || 0} tone="coral" /></div>
          <div className="text-xs text-ink/60">Solver: {p.solver} · distances: {p.distance_basis}</div>
          <MapView height={420} markers={p.routes.flatMap((r: any, i: number) => r.stops.map((s: any) => ({ lat: s.lat, lng: s.lng, color: COLORS[i % COLORS.length], radius: 6, label: `${r.vehicle_code}: ${s.label}<br/>${s.demand_kg} kg · P${s.priority}` })))} polylines={p.routes.map((r: any, i: number) => ({ color: COLORS[i % COLORS.length], points: [[r.depot.lat, r.depot.lng], ...r.stops.map((s: any) => [s.lat, s.lng]), [r.depot.lat, r.depot.lng]] }))} />
          <div className="grid md:grid-cols-2 gap-3">{p.routes.map((r: any, i: number) => <div key={r.vehicle_id} className="card"><div className="flex justify-between"><b style={{ color: COLORS[i % COLORS.length] }}>{r.vehicle_code}</b><span className="text-xs">{r.distance_km} km · fuel ≈ {r.est_fuel_l} L (estimate)</span></div><div className="text-xs text-ink/60">Load {fmt(r.load_kg, 0)}/{fmt(r.capacity_kg, 0)} kg ({r.load_pct}%) · from {r.depot.label}</div><ol className="list-decimal pl-5 text-sm mt-2">{r.stops.map((s: any) => <li key={s.type + s.id}>{s.label} <span className="text-xs text-ink/50">· {s.demand_kg} kg · P{s.priority}{s.demand_note ? ` · ${s.demand_note}` : ""}</span></li>)}</ol></div>)}</div>
          {p.unserved?.length > 0 && <Notice t="red">Unserved: {p.unserved.map((u: any) => u.label || u.id).join("; ")}</Notice>}
          {plan.approval_id && <div className="card flex flex-wrap items-center justify-between gap-2"><div><b>Human approval required</b><div className="text-sm text-ink/70">Approve to mark this plan as dispatched <u>in simulation</u>.</div></div><div className="flex gap-2"><button className="btn-primary" onClick={() => decide(true)} disabled={a.busy}>Approve plan</button><button className="btn-danger" onClick={() => decide(false)} disabled={a.busy}>Reject</button><Link className="btn-secondary" to={`/agents?run=${plan.run_id}`}>Agent trace</Link></div></div>}
        </>)}
        {!p && <div className="card"><Empty title="No plan generated yet" hint="Pending pickups and open hotspot reports are routed to available vehicles by priority." /></div>}
      </>)}
      {tab === "demand" && <Load state={dem}>{(d: any) => (<><Notice>Forecast: {d.forecast.model} · holdout MAPE {fmt((d.forecast.holdout_mape || 0) * 100)}% · trained on <b>simulated</b> history. <DataBadge cls={d.forecast.data_class} /></Notice><div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Ward</th><th className="th">Forecast t/day</th><th className="th">Fleet capacity t/day</th><th className="th">Utilisation</th><th className="th">Vehicles</th><th className="th">Pending pickups</th><th className="th">Risk</th></tr></thead><tbody>{d.wards.map((w: any) => <tr key={w.ward_id}><td className="td">{w.ward}</td><td className="td">{fmt(w.forecast_t_per_day)}</td><td className="td">{fmt(w.capacity_t_per_day)}</td><td className="td">{w.utilisation != null ? `${Math.round(w.utilisation * 100)}%` : "—"}</td><td className="td">{w.vehicles}</td><td className="td">{w.pending_pickups} ({fmt(w.pending_kg, 0)} kg)</td><td className="td">{w.overflow_risk ? <Pill t="red">overflow risk</Pill> : <Pill t="green">ok</Pill>}</td></tr>)}</tbody></table></div></>)}</Load>}
      {tab === "fleet" && <Load state={veh}>{(rows: any[]) => <div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Vehicle</th><th className="th">Ward</th><th className="th">Capacity</th><th className="th">Status</th><th className="th">GPS</th><th className="th"></th></tr></thead><tbody>{rows.map((v) => <tr key={v.id}><td className="td">{v.code}</td><td className="td">{v.ward}</td><td className="td">{v.capacity_kg} kg</td><td className="td"><StatusPill s={v.status} /></td><td className="td text-xs text-ink/50">not connected</td><td className="td"><select className="input w-36 py-1" aria-label={`Status ${v.code}`} value={v.status} onChange={(e) => api.patch(`/vehicles/${v.id}?status=${e.target.value}`).then(veh.reload)}><option value="available">available</option><option value="on_route">on route</option><option value="maintenance">maintenance</option></select></td></tr>)}</tbody></table></div>}</Load>}
      {tab === "history" && <Load state={routes} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => <div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Plan</th><th className="th">Vehicle</th><th className="th">Distance</th><th className="th">Load</th><th className="th">Status</th></tr></thead><tbody>{rows.map((r) => <tr key={r.id}><td className="td">{r.plan_group}</td><td className="td">{r.vehicle}</td><td className="td">{r.distance_km} km</td><td className="td">{r.load_kg} kg</td><td className="td"><StatusPill s={r.status} /></td></tr>)}</tbody></table></div>}</Load>}
    </Page>
  );
}
