import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { DataBadge, Load, Notice, Page, Pill, useLoad } from "../components/ui";

export default function Special() {
  const g = useLoad("/special/guide");
  const f = useLoad("/special/facilities");
  return (
    <Page title="E-waste & Special-Care Waste" subtitle="Batteries, CFLs, electronics, medicines, sanitary and other hazardous items need authorised handling.">
      <Notice t="red" icon={<ShieldAlert size={16} className="mt-0.5" />}>VYARTHX never declares a hazardous item “safe”. Do not open, crush or burn these items. When unsure, keep it aside and use an authorised channel.</Notice>
      <Load state={g}>{(d: any) => (
        <>
          <div className="card"><h2 className="font-bold mb-2">Rules</h2><ul className="list-disc pl-5 text-sm space-y-1">{d.rules.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul></div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{d.items.map((i: any) => (
            <div key={i.id} className="card !p-4"><div className="flex justify-between"><b>{i.name}</b>{i.hazard && <Pill t="red">hazard</Pill>}</div><p className="text-sm mt-1 text-ink/80">{i.handling}</p><p className="text-xs mt-1 text-ink/60"><b>Disposal:</b> {i.disposal}</p></div>
          ))}</div>
        </>
      )}</Load>
      <div className="card"><h2 className="font-bold mb-2">Authorised-type facilities <span className="text-xs font-normal text-ink/50">(demo placements — simulated)</span></h2>
        <Load state={f} emptyIf={(x: any[]) => x.length === 0}>{(rows: any[]) => rows.map((x) => <div key={x.id} className="flex justify-between border-b last:border-0 py-2 text-sm"><div><b>{x.name}</b><div className="text-xs text-ink/60">{x.type} · accepts {x.accepts?.join(", ")}</div><div className="text-xs text-ink/50">{x.authorisation_note}</div></div><DataBadge cls={x.data_class} /></div>)}</Load>
      </div>
      <div className="flex gap-2"><Link to="/doctor" className="btn-primary">Identify an item</Link><Link to="/hotspots" className="btn-secondary">Report unattended hazardous waste</Link></div>
    </Page>
  );
}
