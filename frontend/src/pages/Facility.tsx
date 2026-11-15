import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Empty, ErrorBox, Load, Modal, Notice, Page, Pill, Stat, StatusPill, useAction, useLoad, fmt } from "../components/ui";

export default function FacilityPortal() {
  const { user } = useAuth();
  const inc = useLoad("/facility/incoming");
  const a = useAction();
  const [rec, setRec] = useState<any>(null);
  const [proc, setProc] = useState<any>(null);
  const [v, setV] = useState<any>({});
  const [out, setOut] = useState<any>(null);
  const receive = () => a.run(async () => { const r = await api.post(`/facility/batches/${rec.id}/receive`, { received_kg: Number(v.received_kg), note: v.note || "" }); setOut(r); setRec(null); inc.reload(); });
  const process = () => a.run(async () => { const r = await api.post(`/facility/batches/${proc.id}/process`, { recovered_kg: Number(v.recovered_kg || 0), rejects_kg: Number(v.rejects_kg || 0), loss_kg: Number(v.loss_kg || 0), other_kg: Number(v.other_kg || 0), residual_destination: v.residual_destination || "", note: v.note || "" }); setOut(r); setProc(null); inc.reload(); });
  const sum = ["recovered_kg", "rejects_kg", "loss_kg", "other_kg"].reduce((s, k) => s + Number(v[k] || 0), 0);
  const cap = (id: number, body: any) => a.run(async () => { await api.patch(`/facilities/${id}/capacity`, body); inc.reload(); });
  return (
    <Page title="Facility Desk" subtitle="Confirm receipt and record what was actually recovered. Only these facility-confirmed quantities count towards recovery and final bonuses.">
      {a.err && <ErrorBox error={a.err} />}
      {out && <Notice t={out.run_status === "completed" ? "green" : "amber"}>{out.summary} {out.reason && <b>{out.reason}</b>} {out.final_reward?.credited ? `Final recovery bonus ${out.final_reward.credited} pts credited.` : ""} <Link className="underline" to={`/agents?run=${out.run_id}`}>Agent trace</Link></Notice>}
      <Load state={inc}>{(d: any) => (<>
        {d.facility ? (
          <div className="card"><div className="flex flex-wrap justify-between gap-2"><div><h2 className="font-bold text-lg">{d.facility.name}</h2><div className="text-sm text-ink/60">{d.facility.type} · {d.facility.authorisation_note} {d.facility.authorised ? <Pill t="green">authorised</Pill> : <Pill t="red">not authorised</Pill>}</div></div>
            <div className="flex items-center gap-2 text-sm"><label className="flex items-center gap-1"><input type="checkbox" checked={d.facility.downtime} onChange={(e) => cap(d.facility.id, { downtime: e.target.checked })} />Under downtime</label></div></div>
            <div className="grid grid-cols-3 gap-3 mt-3"><Stat label="Capacity" value={`${d.facility.capacity_tpd} t/day`} badge={d.facility.data_class} /><Stat label="Load" value={`${d.facility.load_tpd} t/day`} tone="blue" /><Stat label="Utilisation" value={`${Math.round((d.facility.load_tpd / d.facility.capacity_tpd) * 100)}%`} tone="amber" /></div></div>
        ) : <Notice t="amber">No facility is linked to your account.</Notice>}
        <div className="card"><h3 className="font-bold mb-2">Incoming & in-process batches</h3>
          {d.batches.length === 0 ? <Empty title="No batches" hint="Batches appear after collectors confirm pickups." /> : <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Passport</th><th className="th">Material</th><th className="th">Input</th><th className="th">Status</th><th className="th">Mass balance</th><th className="th"></th></tr></thead><tbody>
            {d.batches.map((b: any) => <tr key={b.id}><td className="td"><Link className="underline text-deep" to={`/passports?ref=${b.code}`}>{b.code}</Link></td><td className="td">{b.material_key || b.stream}</td><td className="td">{b.input_kg} kg</td><td className="td"><StatusPill s={b.status} /></td><td className="td text-xs">{b.mass_balance.complete ? "closed ✔" : `unaccounted ${fmt(b.mass_balance.discrepancy_kg, 2)} kg`}</td>
              <td className="td whitespace-nowrap">{b.status === "collected" && <button className="btn-primary btn-sm" onClick={() => { setRec(b); setV({ received_kg: b.input_kg }); }}>Confirm receipt</button>}{["at_facility", "processing"].includes(b.status) && <button className="btn-blue btn-sm" onClick={() => { setProc(b); setV({ recovered_kg: "", rejects_kg: "", loss_kg: "", other_kg: "" }); }}>Record processing</button>}</td></tr>)}
          </tbody></table></div>}
        </div></>)}</Load>
      <Modal open={!!rec} onClose={() => setRec(null)} title={`Receive ${rec?.code}`}><div className="space-y-3"><div><label className="label">Weighed at facility (kg)</label><input type="number" step="0.01" className="input" value={v.received_kg ?? ""} onChange={(e) => setV({ ...v, received_kg: e.target.value })} /></div><div className="text-xs text-ink/60">Declared by collector: {rec?.input_kg} kg. A large mismatch is flagged in the passport.</div><div><label className="label">Note</label><input className="input" value={v.note || ""} onChange={(e) => setV({ ...v, note: e.target.value })} /></div><div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setRec(null)}>Cancel</button><button className="btn-primary" disabled={a.busy || !v.received_kg} onClick={receive}>Confirm receipt</button></div></div></Modal>
      <Modal open={!!proc} onClose={() => setProc(null)} title={`Processing record — ${proc?.code}`}><div className="space-y-3">
        <Notice>Input = Recovered + Rejects + Loss/moisture + Other. Currently <b>{fmt(sum, 2)}</b> of <b>{proc?.input_kg}</b> kg accounted. The record is rejected (escalated) if it doesn’t balance.</Notice>
        <div className="grid grid-cols-2 gap-3">{[["recovered_kg", "Recovered material (kg)"], ["rejects_kg", "Rejects (kg)"], ["loss_kg", "Process loss / moisture (kg)"], ["other_kg", "Other recorded output (kg)"]].map(([k, l]) => <div key={k}><label className="label">{l}</label><input type="number" step="0.01" min="0" className="input" value={v[k] ?? ""} onChange={(e) => setV({ ...v, [k]: e.target.value })} /></div>)}</div>
        <div><label className="label">Where do rejects/residual go?</label><input className="input" value={v.residual_destination || ""} onChange={(e) => setV({ ...v, residual_destination: e.target.value })} placeholder="e.g. sanitary landfill, RDF plant" /></div>
        {a.err && <ErrorBox error={a.err} />}
        <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setProc(null)}>Cancel</button><button className="btn-primary" disabled={a.busy} onClick={process}>Submit record</button></div></div></Modal>
    </Page>
  );
}
