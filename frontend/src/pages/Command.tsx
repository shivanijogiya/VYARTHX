import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import MapView from "../components/MapView";
import { DataBadge, ErrorBox, Load, Notice, Page, Pill, Stat, StatusPill, Tabs, useAction, useLoad, when, fmt } from "../components/ui";
import { useState } from "react";

export default function Command() {
  const [days, setDays] = useState(30);
  const ov = useLoad(`/municipal/overview?days=${days}`, [days]);
  const wards = useLoad(`/municipal/wards?days=${days}`, [days]);
  const rec = useLoad("/municipal/recommendations");
  const ts = useLoad("/municipal/timeseries?days=60");
  const ap = useLoad("/approvals?status=pending");
  const [tab, setTab] = useState("overview");
  const a = useAction();
  const decide = (id: number, approve: boolean) => a.run(async () => { await api.post(`/approvals/${id}/decide`, { approve, note: approve ? "Approved in Command Centre" : "Rejected in Command Centre" }); ap.reload(); rec.reload(); });
  const sev: any = { critical: "red", high: "red", medium: "amber", info: "blue", low: "gray" };
  return (
    <Page title="Municipal Command Centre" subtitle="City-wide operations view. Baseline city figures are simulated until real municipal feeds are connected — every metric carries its data class."
      actions={<select className="input w-36" aria-label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))}>{[7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>Last {d} days</option>)}</select>}>
      {a.err && <ErrorBox error={a.err} />}
      <Load state={ov}>{(d: any) => (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{d.metrics.slice(0, 8).map((m: any) => <Stat key={m.key} label={m.label} value={`${fmt(m.value)} ${m.unit === "%" ? "%" : m.unit}`} sub={`${m.period} · ${m.source}`} badge={m.data_class} />)}</div>
          <Notice t="amber">{d.disclaimer}</Notice>
          <div className="grid lg:grid-cols-4 gap-3">
            <Stat label="Pending pickups" value={d.platform.pending_pickups} tone="amber" badge={d.platform.data_class} />
            <Stat label="Open complaints" value={d.pending_complaints} tone="coral" />
            <Stat label="Vehicles available" value={`${d.vehicles.available}/${d.vehicles.total}`} sub={`GPS connected: ${d.vehicles.gps_connected} (none in demo)`} tone="blue" />
            <Stat label="Verified recovered (platform)" value={`${fmt(d.platform.recovered_kg)} kg`} sub="facility-confirmed only" badge={d.platform.data_class} />
          </div>
        </>
      )}</Load>
      <Tabs value={tab} onChange={setTab} tabs={[["overview", "Wards & map"], ["trend", "Trends"], ["recs", "Recommendations"], ["approvals", `Approvals${ap.data?.length ? ` (${ap.data.length})` : ""}`], ["fac", "Facilities"]]} />
      {tab === "overview" && <Load state={wards}>{(rows: any[]) => (
        <div className="grid xl:grid-cols-2 gap-4">
          <MapView height={420} markers={rows.map((w) => ({ lat: w.lat, lng: w.lng, color: w.collection_completion_pct < 85 ? "#F97373" : w.residual_share_pct > 60 ? "#F59E0B" : "#22C55E", radius: 8 + w.pending_complaints / 2, label: `<b>${w.ward}</b><br/>Collection ${w.collection_completion_pct}%<br/>Segregation ${w.segregation_pct}%<br/>Complaints ${w.pending_complaints}` }))} />
          <div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Ward</th><th className="th">t/day</th><th className="th">Collected</th><th className="th">Segregated</th><th className="th">Residual</th><th className="th">Complaints</th><th className="th">Repeat</th></tr></thead><tbody>
            {rows.map((w) => <tr key={w.ward_id}><td className="td font-medium">{w.ward}</td><td className="td">{fmt(w.generated_t_per_day)}</td><td className="td">{fmt(w.collection_completion_pct, 0)}%</td><td className="td">{fmt(w.segregation_pct, 0)}%</td><td className="td">{fmt(w.residual_share_pct, 0)}%</td><td className="td">{w.pending_complaints}</td><td className="td">{w.repeat_hotspots > 0 ? <Pill t="red">{w.repeat_hotspots}</Pill> : "—"}</td></tr>)}
          </tbody></table><div className="text-[11px] text-ink/50 mt-2 flex items-center gap-1">Ward figures: <DataBadge cls={rows[0]?.data_class} /> Locality centroids are approximate.</div></div>
        </div>)}</Load>}
      {tab === "trend" && <Load state={ts}>{(d: any) => <div className="card"><h3 className="font-bold mb-2 flex items-center gap-2">City flow (t/day) <DataBadge cls={d.data_class} /></h3><div className="h-72"><ResponsiveContainer><AreaChart data={d.rows}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="day" fontSize={10} tickFormatter={(v: string) => v.slice(5)} /><YAxis fontSize={11} /><Tooltip /><Legend /><Area dataKey="generated" name="Generated" stroke="#1D4ED8" fill="#38BDF8" fillOpacity={0.25} /><Area dataKey="collected" name="Collected" stroke="#166534" fill="#22C55E" fillOpacity={0.3} /><Area dataKey="residual" name="Residual to landfill" stroke="#F97373" fill="#F97373" fillOpacity={0.25} /></AreaChart></ResponsiveContainer></div></div>}</Load>}
      {tab === "recs" && <Load state={rec} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => <div className="grid md:grid-cols-2 gap-3">{rows.map((r) => <div key={r.id} className="card"><div className="flex justify-between"><b>{r.title}</b><Pill t={sev[r.severity] || "gray"}>{r.severity}</Pill></div><p className="text-sm text-ink/80 mt-1">{r.detail}</p><div className="mt-2 flex items-center gap-2">{r.action?.to && <Link to={r.action.to} className="btn-secondary btn-sm">{r.action.label || "Open"}</Link>}{r.requires_approval && <Pill t="amber">needs your approval</Pill>}<DataBadge cls={r.data_class} /></div></div>)}</div>}</Load>}
      {tab === "approvals" && <Load state={ap} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => <div className="card"><p className="text-sm text-ink/70 mb-2">Agents can only <b>propose</b> these. Nothing is dispatched or authorised until a human decides.</p>{rows.map((x) => <div key={x.id} className="flex flex-wrap items-center justify-between gap-2 border-b last:border-0 py-3"><div><b className="text-sm">{x.title}</b><div className="text-xs text-ink/60">{x.action.replace(/_/g, " ")} · requested by {x.requested_by_name} · {when(x.created_at)}</div><div className="text-[11px] text-ink/50">{JSON.stringify(x.payload).slice(0, 140)}</div></div><div className="flex gap-2">{x.run_id && <Link className="btn-secondary btn-sm" to={`/agents?run=${x.run_id}`}>Trace</Link>}<button className="btn-primary btn-sm" disabled={a.busy} onClick={() => decide(x.id, true)}>Approve</button><button className="btn-danger btn-sm" disabled={a.busy} onClick={() => decide(x.id, false)}>Reject</button></div></div>)}</div>}</Load>}
      {tab === "fac" && <Load state={ov}>{(d: any) => <div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Facility</th><th className="th">Type</th><th className="th">Capacity</th><th className="th">Load</th><th className="th">Utilisation</th><th className="th">Status</th></tr></thead><tbody>{d.facilities.map((f: any) => <tr key={f.id}><td className="td">{f.name}</td><td className="td">{f.type}</td><td className="td">{f.capacity_tpd} t/d</td><td className="td">{f.load_tpd}</td><td className="td"><div className="w-24 h-2 bg-gray-100 rounded-full"><div className={`h-full rounded-full ${f.utilisation > 0.9 ? "bg-coral" : f.utilisation > 0.75 ? "bg-amber" : "bg-fresh"}`} style={{ width: `${Math.min(100, f.utilisation * 100)}%` }} /></div></td><td className="td">{f.downtime ? <Pill t="red">downtime</Pill> : f.authorised ? <Pill t="green">authorised</Pill> : <Pill t="amber">unauthorised</Pill>} <DataBadge cls={f.data_class} /></td></tr>)}</tbody></table></div>}</Load>}
    </Page>
  );
}
