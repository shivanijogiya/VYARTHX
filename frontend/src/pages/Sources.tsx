import { DataBadge, Load, Notice, Page, Pill, useLoad } from "../components/ui";

export default function Sources() {
  const s = useLoad("/system/status");
  const d = useLoad("/system/datasources");
  return (
    <Page title="Data Sources & Honesty Panel" subtitle="What is real, what is simulated, and what is not connected. VYARTHX never presents simulated or estimated numbers as official.">
      <Load state={s}>{(x: any) => (<>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="card text-sm space-y-1"><h3 className="font-bold mb-1">System status</h3>
            <div>Mode: {x.demo_mode ? <Pill t="purple">Demo Mode (simulated records)</Pill> : <Pill t="blue">Pilot</Pill>}</div>
            <div>Agent orchestration: <b>{x.graph_engine}</b> — {x.agent_mode}</div><div>Database: <b>{x.database}</b></div><div>Routing: {x.routing}</div><div>Forecasting: {x.forecasting}</div><div>Digital Twin: {x.digital_twin}</div></div>
          <div className="card text-sm"><h3 className="font-bold mb-1">Models</h3>{Object.entries(x.models).map(([k, v]: any) => <div key={k} className="py-1 border-b last:border-0"><b>{k.replace(/_/g, " ")}:</b> {typeof v === "object" ? JSON.stringify(v) : String(v)}</div>)}</div>
        </div>
        <div className="card"><h3 className="font-bold mb-2">Integrations</h3><div className="grid sm:grid-cols-2 gap-1 text-sm">{Object.entries(x.integrations).filter(([k]) => k !== "note").map(([k, v]: any) => <div key={k} className="flex justify-between border-b py-1"><span>{k.replace(/_/g, " ")}</span>{v ? <Pill t="green">connected</Pill> : <Pill t="gray">not connected</Pill>}</div>)}</div><div className="text-xs text-ink/60 mt-2">{x.integrations.note}</div></div>
      </>)}</Load>
      <Load state={d}>{(r: any) => (<div className="card overflow-x-auto"><h3 className="font-bold mb-2">Dataset registry</h3>{r.note && <Notice t="amber">{r.note}</Notice>}<table className="w-full mt-2"><thead><tr><th className="th">Source</th><th className="th">Publisher</th><th className="th">Scope / units</th><th className="th">Licence</th><th className="th">Status</th><th className="th">Used for</th></tr></thead><tbody>{(r.sources || []).map((s: any) => <tr key={s.id}><td className="td font-medium">{s.name}{s.url && <div><a className="text-xs text-deep underline" href={s.url} target="_blank" rel="noreferrer">link</a></div>}</td><td className="td">{s.publisher}</td><td className="td text-xs">{s.scope}<div className="text-ink/50">{s.units}</div></td><td className="td text-xs">{s.licence}</td><td className="td"><Pill t={s.status === "retrieved" ? "green" : "amber"}>{s.status}</Pill><div className="text-[10px] text-ink/50 mt-1">{s.status_note}</div></td><td className="td text-xs">{s.used_for} <DataBadge cls={s.data_class || "simulated"} /></td></tr>)}</tbody></table></div>)}</Load>
      <div className="card text-sm"><h3 className="font-bold mb-2">Data classes</h3><div className="flex flex-wrap gap-4"><span><DataBadge cls="official" /> from an official public source</span><span><DataBadge cls="pilot" /> measured in a real pilot</span><span><DataBadge cls="estimate" /> computed with documented assumptions</span><span><DataBadge cls="simulated" /> synthetic demo data</span></div></div>
    </Page>
  );
}
