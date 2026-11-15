import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { DataBadge, ErrorBox, Notice, Page, Pill, Stat, useAction, fmt } from "../components/ui";

export default function Compost() {
  const { user } = useAuth();
  const [f, setF] = useState({ households: 60, kg_per_household_day: 0.5, days: 30, method: "windrow" });
  const [r, setR] = useState<any>(null);
  const a = useAction();
  const go = () => a.run(async () => setR(await api.post("/compost/plan", { ...f, households: Number(f.households), kg_per_household_day: Number(f.kg_per_household_day), days: Number(f.days), ward_id: user.ward_id })));
  const e = r?.estimate;
  return (
    <Page title="Compost-to-Community" subtitle="Plan wet-waste processing for a society, campus or ward. Outputs are estimates until a facility records actual results.">
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card space-y-3">
          <div><label className="label" htmlFor="h">Households / participants</label><input id="h" type="number" min={1} className="input" value={f.households} onChange={(e) => setF({ ...f, households: e.target.value as any })} /></div>
          <div><label className="label" htmlFor="k">Wet waste per household per day (kg)</label><input id="k" type="number" step="0.1" min={0.05} className="input" value={f.kg_per_household_day} onChange={(e) => setF({ ...f, kg_per_household_day: e.target.value as any })} /></div>
          <div><label className="label" htmlFor="d">Days</label><input id="d" type="number" min={1} max={365} className="input" value={f.days} onChange={(e) => setF({ ...f, days: e.target.value as any })} /></div>
          <div><label className="label" htmlFor="m">Method</label><select id="m" className="input" value={f.method} onChange={(e) => setF({ ...f, method: e.target.value })}><option value="windrow">Windrow composting</option><option value="vermicompost">Vermicomposting</option><option value="aerobic_bin">Aerobic bin</option><option value="biomethanation">Biomethanation (biogas)</option></select></div>
          <button className="btn-primary w-full" onClick={go} disabled={a.busy}>{a.busy ? "Planning…" : "Estimate & find facilities"}</button>
          {a.err && <ErrorBox error={a.err} />}
        </div>
        <div className="lg:col-span-2 space-y-4">
          {!e && <div className="card text-sm text-ink/70">Enter your numbers to see feedstock, estimated compost, estimated biogas and the nearest compost/biomethanation facilities with remaining headroom.</div>}
          {e && (<>
            <div className="grid grid-cols-3 gap-3"><Stat label="Feedstock" value={`${fmt(e.feedstock_kg, 0)} kg`} sub={e.formula} /><Stat label="Compost (est.)" value={`${fmt(e.estimated_compost_kg, 0)} kg`} sub={`yield assumption ${e.compost_yield_assumption}`} badge="estimate" tone="blue" /><Stat label="Biogas if routed (est.)" value={`${fmt(e.estimated_biogas_m3_if_biomethanation, 0)} m³`} badge="estimate" tone="amber" /></div>
            <Notice t="amber">{e.label} {e.yield_note}</Notice>
            <div className="card"><h2 className="font-bold mb-2">Nearest facilities</h2>
              {e.facilities?.length ? e.facilities.map((x: any) => <div key={x.facility_id} className="flex justify-between border-b last:border-0 py-2 text-sm"><div><b>{x.name}</b><div className="text-xs text-ink/60">{x.type} · {x.distance_km} km · headroom {x.headroom_t} t/day · utilisation {Math.round(x.utilisation * 100)}%</div></div><DataBadge cls={x.data_class} /></div>) : <div className="text-sm text-ink/60">No facility with enough headroom found.</div>}
              <div className="text-xs text-ink/50 mt-2">Facility placements and capacities in this demo are simulated.</div>
            </div>
            <Pill t="gray">Agent run #{r.run_id}</Pill>
          </>)}
        </div>
      </div>
    </Page>
  );
}
