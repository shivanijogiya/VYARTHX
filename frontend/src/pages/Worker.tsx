import { useState } from "react";
import { Link } from "react-router-dom";
import { QrCode, ShieldCheck, Wallet, Briefcase, CheckCircle2 } from "lucide-react";
import { api, fd } from "../api";
import { DataBadge, Empty, ErrorBox, Load, Modal, Notice, Page, Pill, Stat, StatusPill, Tabs, useAction, useLoad, when, fmt } from "../components/ui";

export default function WorkerPortal() {
  const me = useLoad("/workers/me");
  const tasks = useLoad("/workers/tasks");
  const earn = useLoad("/workers/earnings");
  const hist = useLoad("/workers/history");
  const conn = useLoad("/workers/connections");
  const safety = useLoad("/workers/safety");
  const fac = useLoad("/facilities");
  const [tab, setTab] = useState("tasks");
  const [sel, setSel] = useState<any>(null);
  const [f, setF] = useState<any>({ qr_code: "", weight_kg: "", weight_source: "scale", evidence_note: "" });
  const [photo, setPhoto] = useState<File | null>(null);
  const [out, setOut] = useState<any>(null);
  const [deliver, setDeliver] = useState<any>(null);
  const [fid, setFid] = useState("");
  const a = useAction();
  const all = () => { tasks.reload(); me.reload(); earn.reload(); hist.reload(); };
  const accept = (id: number) => a.run(async () => { await api.post(`/collections/${id}/accept`); all(); });
  const reject = (id: number) => a.run(async () => { await api.post(`/collections/${id}/reject`); all(); });
  const confirm = () => a.run(async () => { const r = await api.form(`/collections/${sel.id}/confirm`, fd({ ...f, weight_kg: f.weight_kg, photo })); setOut(r); setSel(null); setF({ qr_code: "", weight_kg: "", weight_source: "scale", evidence_note: "" }); setPhoto(null); all(); });
  const doDeliver = () => a.run(async () => { await api.post(`/collections/${deliver.id}/deliver`, { facility_id: Number(fid) }); setDeliver(null); all(); });
  const availability = (v: boolean) => a.run(async () => { await api.put(`/workers/me/availability?available=${v}`); me.reload(); });
  const Task = ({ t, mine }: { t: any; mine: boolean }) => (
    <div className="rounded-xl border p-3 mb-2">
      <div className="flex justify-between items-start gap-2"><div><b>{t.detected_object || t.stream}</b> <Pill t={t.stream === "special" ? "red" : t.stream === "wet" ? "green" : "blue"}>{t.stream}</Pill>{t.priority === 1 && <Pill t="red">priority</Pill>}<div className="text-xs text-ink/60 mt-0.5">{t.ward} · ~{t.est_weight_kg} kg · {t.distance_km} km away · {when(t.scheduled_for)}</div></div><StatusPill s={t.status} /></div>
      <div className="mt-2 flex flex-wrap gap-2">
        {!mine && <button className="btn-primary btn-sm" disabled={a.busy} onClick={() => accept(t.id)}>Accept</button>}
        {mine && t.status === "assigned" && <><button className="btn-primary btn-sm" onClick={() => accept(t.id)}>Accept</button><button className="btn-secondary btn-sm" onClick={() => reject(t.id)}>Decline</button></>}
        {mine && t.status === "accepted" && <button className="btn-blue btn-sm" onClick={() => setSel(t)}><QrCode size={14} />Confirm handover</button>}
        <a className="btn-secondary btn-sm" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${t.lat}&mlon=${t.lng}#map=17/${t.lat}/${t.lng}`}>Map</a>
      </div>
    </div>
  );
  return (
    <Page title="Worker Portal" subtitle="Mobile-friendly: accept tasks, confirm handovers by household ID/QR and weight, see transparent earnings.">
      {a.err && <ErrorBox error={a.err} />}
      {out && <Notice t={out.run_status === "completed" ? "green" : "amber"}><b>{out.run_status === "completed" ? "Handover confirmed." : "Needs review."}</b> {out.reason || out.summary}{out.reward?.credited ? ` Citizen credited ${out.reward.credited} verified points.` : ""}{out.passport?.code ? ` Passport ${out.passport.code} created.` : ""} <Link to={`/agents?run=${out.run_id}`} className="underline">Agent trace</Link></Notice>}
      <Load state={me}>{(d: any) => (
        <div className="card">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><div className="text-lg font-bold">{d.name}</div><div className="text-sm text-ink/60">{d.worker_code} · {d.ward} · languages {d.languages?.join(", ")}</div><div className="mt-1 flex flex-wrap gap-1">{d.badges.map((b: string) => <Pill key={b} t="green">{b}</Pill>)}<Pill t="gray">identity: {d.identity_status}</Pill></div></div>
            <div className="text-center"><div className="bg-white border-2 border-forest rounded-lg p-2 inline-block"><QrCode size={56} /><div className="text-[10px] font-mono">{d.digital_id.qr_payload}</div></div></div></div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-4"><Stat label="Pickups done" value={d.pickups_completed} /><Stat label="Verified kg" value={fmt(d.verified_kg)} tone="blue" /><Stat label="Earnings (ledger)" value={`₹${fmt(d.earnings_inr, 0)}`} tone="amber" /><div className="card !p-4 flex items-center justify-between"><div className="text-xs font-semibold">Available for tasks</div><button role="switch" aria-checked={d.available} onClick={() => availability(!d.available)} className={`w-12 h-6 rounded-full relative transition ${d.available ? "bg-fresh" : "bg-gray-300"}`}><span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full transition-all ${d.available ? "left-6" : "left-0.5"}`} /></button></div></div>
          <div className="text-xs text-ink/60 mt-3">{d.inclusion_note}</div>
        </div>
      )}</Load>
      <Tabs value={tab} onChange={setTab} tabs={[["tasks", "Tasks"], ["handover", "Transfer to facility"], ["earnings", "Earnings"], ["connect", "Buyers nearby"], ["safety", "Safety"]]} />
      {tab === "tasks" && <Load state={tasks}>{(d: any) => (<div className="grid md:grid-cols-2 gap-4"><div className="card"><h3 className="font-bold mb-2">My tasks</h3>{d.assigned.length === 0 ? <Empty title="No assigned tasks" /> : d.assigned.map((t: any) => <Task key={t.id} t={t} mine />)}</div><div className="card"><h3 className="font-bold mb-2">Open requests nearby</h3>{d.nearby.length === 0 ? <Empty title="No open requests within 15 km" /> : d.nearby.map((t: any) => <Task key={t.id} t={t} mine={false} />)}</div></div>)}</Load>}
      {tab === "handover" && <div className="card"><h3 className="font-bold mb-2">Confirmed pickups ready to hand to a facility</h3><Load state={hist} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => rows.filter((r) => r.status === "collected").length === 0 ? <Empty title="Nothing waiting" /> : rows.filter((r) => r.status === "collected").map((c) => <div key={c.id} className="flex flex-wrap justify-between items-center border-b last:border-0 py-2 text-sm"><div>#{c.id} · {c.detected_object || c.stream} · {c.verified_weight_kg} kg · passport {c.passport}</div><button className="btn-primary btn-sm" onClick={() => setDeliver(c)}>Record handover to facility</button></div>)}</Load></div>}
      {tab === "earnings" && <Load state={earn}>{(d: any) => <div className="card"><div className="grid grid-cols-2 gap-3 mb-3"><Stat label="Total (ledger)" value={`₹${fmt(d.total_inr, 0)}`} /><Stat label="Last 7 days" value={`₹${fmt(d.last_7d_inr, 0)}`} tone="blue" /></div><Notice>{d.notice}</Notice><table className="w-full mt-2"><thead><tr><th className="th">When</th><th className="th">₹</th><th className="th">Basis</th></tr></thead><tbody>{d.records.map((r: any) => <tr key={r.id}><td className="td">{when(r.created_at)}</td><td className="td font-bold">₹{r.amount_inr}</td><td className="td text-ink/70">{r.note}</td></tr>)}</tbody></table></div>}</Load>}
      {tab === "connect" && <Load state={conn} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => <div className="card"><h3 className="font-bold mb-2">Recycler / buyer demand near you</h3>{rows.map((r) => <div key={r.listing_id} className="flex justify-between border-b last:border-0 py-2 text-sm"><div><b>{r.buyer}</b><div className="text-xs text-ink/60">{r.material} · wants {fmt(r.wanted_kg, 0)} kg · {r.distance_km} km</div></div><div className="text-right">{r.price_inr_per_kg != null ? `₹${r.price_inr_per_kg}/kg` : "—"}<div className="text-[10px] text-ink/40 max-w-[10rem]">{r.price_note}</div></div></div>)}</div>}</Load>}
      {tab === "safety" && <Load state={safety}>{(rows: any[]) => <div className="grid md:grid-cols-2 gap-3">{rows.map((s) => <div key={s.title} className="card !p-4"><div className="font-bold flex items-center gap-2"><ShieldCheck size={16} className="text-fresh" />{s.title}</div><p className="text-sm mt-1 text-ink/80">{s.body}</p></div>)}</div>}</Load>}
      <Modal open={!!sel} onClose={() => setSel(null)} title={`Confirm handover #${sel?.id}`}>
        <div className="space-y-3"><Notice>Ask the household to show their ID/QR. Weight confirmed here decides the citizen’s verified points and your fee.</Notice>
          <div><label className="label" htmlFor="qr">Household QR / ID code</label><input id="qr" className="input font-mono" placeholder="VX-HH-0001" value={f.qr_code} onChange={(e) => setF({ ...f, qr_code: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-3"><div><label className="label" htmlFor="wk">Weight (kg)</label><input id="wk" type="number" step="0.1" min="0.05" className="input" value={f.weight_kg} onChange={(e) => setF({ ...f, weight_kg: e.target.value })} /></div><div><label className="label" htmlFor="ws">Weight source</label><select id="ws" className="input" value={f.weight_source} onChange={(e) => setF({ ...f, weight_source: e.target.value })}><option value="scale">Scale</option><option value="manual_entry">Manual estimate</option></select></div></div>
          <div><label className="label" htmlFor="nt">Note</label><input id="nt" className="input" value={f.evidence_note} onChange={(e) => setF({ ...f, evidence_note: e.target.value })} /></div>
          <div><label className="label" htmlFor="ph">Photo evidence (optional)</label><input id="ph" type="file" accept="image/*" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] || null)} className="text-sm" /></div>
          {a.err && <ErrorBox error={a.err} />}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setSel(null)}>Cancel</button><button className="btn-primary" disabled={a.busy || !f.weight_kg} onClick={confirm}><CheckCircle2 size={16} />Confirm</button></div></div>
      </Modal>
      <Modal open={!!deliver} onClose={() => setDeliver(null)} title="Hand over to facility"><div className="space-y-3"><div><label className="label" htmlFor="fc">Authorised facility</label><select id="fc" className="input" value={fid} onChange={(e) => setFid(e.target.value)}><option value="">Select…</option>{fac.data?.filter((x: any) => x.authorised && !x.downtime).map((x: any) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div><div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setDeliver(null)}>Cancel</button><button className="btn-primary" disabled={!fid || a.busy} onClick={doDeliver}>Record</button></div></div></Modal>
    </Page>
  );
}
