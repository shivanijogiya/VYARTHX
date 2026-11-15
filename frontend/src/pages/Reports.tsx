import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getToken } from "../api";
import { useAuth } from "../auth";
import { DataBadge, Load, Notice, Page, Pill, Stat, useLoad, fmt } from "../components/ui";

const COL = ["#0866FF", "#31A24C", "#38BDF8", "#7B61FF", "#F7B928", "#F02849", "#A78BFA"];
export default function Reports() {
  const { user } = useAuth();
  const [days, setDays] = useState(90);
  const imp = useLoad(`/reports/impact?days=${days}`, [days]);
  const mun = useLoad(user.role === "municipal" ? `/reports/municipal?days=${Math.min(days, 90)}` : null, [days]);
  const csv = async () => { const r = await fetch(`/api/reports/municipal?format=csv&days=${days}`, { headers: { Authorization: `Bearer ${getToken()}` } }); const b = await r.blob(); const u = URL.createObjectURL(b); const a = document.createElement("a"); a.href = u; a.download = "vyarthx_municipal_report.csv"; a.click(); };
  return (
    <Page title="Analytics & Impact Reports" subtitle="Impact is counted only from verified collections and facility-confirmed recovery. Every figure states its source and data class."
      actions={<><select className="input w-36" aria-label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))}>{[30, 60, 90, 180].map((d) => <option key={d} value={d}>Last {d} days</option>)}</select>{user.role === "municipal" && <><button className="btn-secondary" onClick={csv}>Download CSV</button><button className="btn-primary" onClick={() => window.print()}>Print / Save PDF</button></>}</>}>
      <Load state={imp}>{(d: any) => {
        const mat = Object.entries(d.recovered_by_material_kg || {}).map(([k, v]) => ({ name: k.replace(/_/g, " "), kg: Number(v) }));
        return (<>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3"><Stat label="Verified collected" value={`${fmt(d.verified_collected_kg)} kg`} badge={d.data_class} /><Stat label="Facility-confirmed recovered" value={`${fmt(d.facility_confirmed_recovered_kg)} kg`} tone="blue" badge={d.data_class} /><Stat label="CO₂e avoided (illustrative)" value={`${fmt(d.estimated_co2e_avoided_kg)} kg`} tone="amber" badge="estimate" /><Stat label="Batches with facility confirmation" value={`${d.batches_with_facility_confirmation}/${d.batches}`} /></div>
          <div className="grid lg:grid-cols-2 gap-4"><div className="card"><h3 className="font-bold mb-2">Recovered by material (kg)</h3><div className="h-64"><ResponsiveContainer><BarChart data={mat}><CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey="name" fontSize={10} interval={0} /><YAxis fontSize={11} /><Tooltip /><Bar dataKey="kg" fill="#31A24C" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></div>
            <div className="card"><h3 className="font-bold mb-2">Method & caveats</h3><p className="text-sm text-ink/80">{d.method}</p><p className="text-sm text-ink/80 mt-2">{d.co2e_note}</p></div></div>
        </>);
      }}</Load>
      {user.role === "municipal" && <Load state={mun}>{(d: any) => (<>
        <div className="card overflow-x-auto"><h3 className="font-bold mb-2">City metrics</h3><table className="w-full"><thead><tr><th className="th">Metric</th><th className="th">Value</th><th className="th">Period</th><th className="th">Source</th><th className="th">Class</th></tr></thead><tbody>{d.overview.metrics.map((m: any) => <tr key={m.key}><td className="td">{m.label}</td><td className="td font-semibold">{fmt(m.value)} {m.unit}</td><td className="td">{m.period}</td><td className="td text-xs text-ink/60">{m.source}</td><td className="td"><DataBadge cls={m.data_class} /></td></tr>)}</tbody></table></div>
        <div className="card overflow-x-auto"><h3 className="font-bold mb-2">Ward comparison</h3><div className="h-72"><ResponsiveContainer><BarChart data={d.wards}><CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey="ward" fontSize={9} interval={0} angle={-30} textAnchor="end" height={60} /><YAxis fontSize={11} /><Tooltip /><Legend /><Bar dataKey="collection_completion_pct" name="Collection %" fill="#0866FF" /><Bar dataKey="segregation_pct" name="Segregation %" fill="#31A24C" /><Bar dataKey="residual_share_pct" name="Residual %" fill="#F02849" /></BarChart></ResponsiveContainer></div></div>
        <Notice>Generated {new Date(d.generated_at).toLocaleString("en-IN")} · {d.overview.disclaimer}</Notice>
      </>)}</Load>}
    </Page>
  );
}
