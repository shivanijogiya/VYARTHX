import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { DataBadge, Load, Notice, Page, Pill, Stat, useLoad, fmt } from "../components/ui";

const tone: any = { critical: "red", watch: "amber", ok: "green" };
export default function Landfill() {
  const l = useLoad("/landfill");
  return (
    <Page title="Landfill Intelligence" subtitle="How fast residual waste is consuming reported disposal capacity — and which diversion actions buy the most time.">
      <Load state={l}>{(d: any) => (<>
        <Notice t="amber">{d.capacity_disclaimer}</Notice>
        <div className="grid md:grid-cols-2 gap-4">{d.sites.map((s: any) => (
          <div key={s.id} className="card">
            <div className="flex justify-between gap-2"><div><b>{s.name}</b><div className="text-xs text-ink/60">{s.type}</div></div><Pill t={tone[s.capacity_class] || "gray"}>{s.capacity_label || s.capacity_class}</Pill></div>
            <div className="grid grid-cols-3 gap-3 mt-3"><Stat label="Remaining" value={`${fmt(s.remaining_pct, 0)}%`} sub={`${fmt(s.remaining_capacity_t, 0)} t`} badge="simulated" /><Stat label="Inflow (t/day)" value={fmt(s.daily_incoming_t, 0)} sub={`forecast ${fmt(s.forecast_incoming_t_per_day, 0)}`} tone="blue" /><Stat label="Days to capacity" value={fmt(s.estimated_days_to_capacity, 0)} tone="coral" badge="estimate" /></div>
            {s.trend?.length > 1 && <div className="h-32 mt-2"><ResponsiveContainer><LineChart data={s.trend.map((v: any, i: number) => ({ i, v: typeof v === "number" ? v : v.t ?? v.value }))}><CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey="i" hide /><YAxis width={40} fontSize={10} /><Tooltip /><Line dataKey="v" stroke="#F97373" dot={false} strokeWidth={2} /></LineChart></ResponsiveContainer></div>}
            <div className="text-[11px] text-ink/50 mt-1">{s.note}</div>
          </div>))}</div>
        <div className="card"><h3 className="font-bold mb-2">Diversion opportunities</h3><div className="text-xs text-ink/60 mb-2">{d.forecast_note}</div>{d.diversion_opportunities.map((o: any, i: number) => <div key={i} className="flex justify-between border-b last:border-0 py-2 text-sm"><div><b>{o.title}</b><div className="text-xs text-ink/60">{o.basis}</div></div><Pill t="green">−{fmt(o.est_residual_reduction_t_per_day)} t/day</Pill></div>)}<div className="mt-3 flex gap-2 items-center"><Link to="/twin" className="btn-primary">Test in Digital Twin</Link><span className="text-xs text-ink/60">Recent residual ratio: {fmt((d.residual_ratio_recent || 0) * 100, 0)}% · model: {d.forecast_model}</span></div></div>
      </>)}</Load>
    </Page>
  );
}
