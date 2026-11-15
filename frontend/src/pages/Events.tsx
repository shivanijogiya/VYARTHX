import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Empty, ErrorBox, Load, Modal, Notice, Page, Pill, Stat, StatusPill, useAction, useLoad, when, fmt } from "../components/ui";

export default function Events() {
  const { user } = useAuth();
  const list = useLoad("/events");
  const [sel, setSel] = useState<number | null>(null);
  const det = useLoad(sel ? `/events/${sel}` : null, [sel]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<any>({ name: "", venue: "", category: "college", starts_at: "", duration_h: 4, expected_attendance: 200, food: "packaged", volunteers_available: 5, sponsor_requirements: "" });
  const [joinRole, setJoinRole] = useState("volunteer");
  const [w, setW] = useState<any>({ stream: "wet", kg: 10, destination: "", recovered: true });
  const [report, setReport] = useState<any>(null);
  const a = useAction();
  const create = () => a.run(async () => { const r = await api.post("/events", { ...f, starts_at: new Date(f.starts_at).toISOString().slice(0, 19), duration_h: Number(f.duration_h), expected_attendance: Number(f.expected_attendance), volunteers_available: Number(f.volunteers_available), ward_id: user.ward_id }); setOpen(false); list.reload(); setSel(r.event.id); });
  const join = () => a.run(async () => { await api.post(`/events/${sel}/join`, { role: joinRole, org_name: "", contribution_inr: 0 }); det.reload(); });
  const logw = () => a.run(async () => { await api.post(`/events/${sel}/waste`, { ...w, kg: Number(w.kg) }); det.reload(); });
  const complete = () => a.run(async () => { setReport(await api.post(`/events/${sel}/complete`)); det.reload(); list.reload(); });
  const e = det.data;
  const canLog = e && (e.mine || ["municipal", "facility"].includes(user.role));
  return (
    <Page title="Zero-Waste Events" subtitle="Plan waste per event, recruit volunteers and partners, log segregated waste — and earn a certificate only with verified evidence."
      actions={<button className="btn-primary" onClick={() => setOpen(true)}>+ Plan an event</button>}>
      {a.err && <ErrorBox error={a.err} />}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card lg:col-span-1 max-h-[78vh] overflow-auto"><h2 className="font-bold mb-2">Events</h2>
          <Load state={list} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => rows.map((x) => (
            <button key={x.id} onClick={() => { setSel(x.id); setReport(null); }} className={`w-full text-left rounded-lg p-2.5 mb-1 hover:bg-hover transition-colors ${sel === x.id ? "!bg-mint" : ""}`}>
              <div className="flex justify-between"><b className="text-sm">{x.name}</b><StatusPill s={x.status} /></div><div className="text-xs text-ink/60">{when(x.starts_at)} · {x.expected_attendance} people · {x.participants} participants</div>
            </button>))}</Load></div>
        <div className="lg:col-span-2 space-y-4">
          {!sel && <div className="card"><Empty title="Select an event" hint="Or plan a new one to get an AI-estimated waste plan." /></div>}
          {sel && <Load state={det}>{(e: any) => (<>
            <div className="card"><div className="flex flex-wrap justify-between gap-2"><div><h2 className="text-lg font-bold text-ink">{e.name}</h2><div className="text-sm text-ink/60">{e.venue} · {e.ward} · {when(e.starts_at)} · {e.duration_h}h · food: {e.food} · organiser {e.organiser}</div></div><StatusPill s={e.status} /></div>
              <h3 className="font-semibold mt-4 text-sm">Event Planning Agent’s waste plan <Pill t="amber">estimate</Pill></h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-2"><Stat label="Expected waste" value={`${fmt(e.plan?.estimated_total_kg, 0)} kg`} /><Stat label="Collection points" value={e.plan?.collection_points} tone="blue" /><Stat label="Volunteers needed" value={e.plan?.volunteers_required} sub={`${e.volunteers_available} available`} tone="amber" /><Stat label="Participants" value={e.participants} /></div>
              {e.plan?.estimated_by_stream_kg && <div className="text-xs mt-2 text-ink/70">By stream: {Object.entries(e.plan.estimated_by_stream_kg).map(([k, v]) => `${k.replace("_", " ")} ${v} kg`).join(" · ")}</div>}
              {e.plan?.partners?.length > 0 && <div className="mt-2 text-sm"><b>Suggested partners</b> (not confirmed): {e.plan.partners.map((p: any) => `${p.name} (${p.for})`).join("; ")}</div>}
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="card"><h3 className="font-bold mb-2">Join this event</h3><div className="flex gap-2"><select className="input" aria-label="Role" value={joinRole} onChange={(x) => setJoinRole(x.target.value)}>{["volunteer", "attendee", "sponsor", "collection_partner", "recycler"].map((r) => <option key={r}>{r}</option>)}</select><button className="btn-primary" onClick={join} disabled={a.busy}>Join</button></div>
                <div className="mt-3 text-sm space-y-1">{e.participation.length === 0 ? <span className="text-ink/60">No one yet.</span> : e.participation.map((p: any) => <div key={p.id} className="flex justify-between"><span>{p.name} · {p.role}</span><StatusPill s={p.status} /></div>)}</div></div>
              <div className="card"><h3 className="font-bold mb-2">Waste log</h3>
                {e.waste_log.length === 0 ? <div className="text-sm text-ink/60">Nothing logged yet.</div> : <table className="w-full"><tbody>{e.waste_log.map((x: any) => <tr key={x.id}><td className="td">{x.stream}</td><td className="td">{x.kg} kg</td><td className="td">{x.recovered ? "recovered" : "disposed"}</td><td className="td">{x.verified ? <Pill t="green">verified</Pill> : <Pill t="amber">reported</Pill>}</td></tr>)}</tbody></table>}
                {canLog && e.status !== "completed" && <div className="mt-3 flex flex-wrap gap-2 items-end"><select className="input w-32" aria-label="Stream" value={w.stream} onChange={(x) => setW({ ...w, stream: x.target.value })}>{["wet", "dry_recyclable", "reject", "special", "reusable"].map((s) => <option key={s}>{s}</option>)}</select><input type="number" min={0.1} className="input w-20" aria-label="kg" value={w.kg} onChange={(x) => setW({ ...w, kg: x.target.value })} /><label className="text-xs flex items-center gap-1"><input type="checkbox" checked={w.recovered} onChange={(x) => setW({ ...w, recovered: x.target.checked })} />recovered</label><button className="btn-secondary btn-sm" onClick={logw}>Log</button></div>}
              </div>
            </div>
            {canLog && e.status !== "completed" && <button className="btn-blue" onClick={complete} disabled={a.busy}>Complete event & generate report</button>}
            {(report || e.status === "completed") && (() => { const rep = report?.report || e.report; const cert = report?.certificate || e.certificate; return rep?.totals ? (
              <div className="card"><h3 className="font-bold mb-2">Post-event report</h3><div className="grid grid-cols-2 sm:grid-cols-4 gap-3"><Stat label="Total waste" value={`${fmt(rep.totals.total_kg, 0)} kg`} /><Stat label="Verified" value={`${fmt(rep.totals.verified_kg, 0)} kg`} tone="blue" /><Stat label="Diversion (verified)" value={`${Math.round((rep.totals.diversion_verified || 0) * 100)}%`} /><Stat label="Diversion (reported)" value={`${Math.round((rep.totals.diversion_reported || 0) * 100)}%`} tone="amber" /></div>
                {cert?.issued ? <Notice t="green"><b>Zero-Waste certificate issued</b> — verified evidence supports ≥ the diversion threshold. ({cert.code})</Notice> : <Notice t="amber"><b>No certificate yet.</b> {(rep.certificate_blockers || cert?.blockers || []).join(" · ")} Organiser-reported figures alone cannot earn a certificate.</Notice>}</div>) : null; })()}
          </>)}</Load>}
        </div>
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Plan an event" wide><div className="grid sm:grid-cols-2 gap-3">
        <div className="sm:col-span-2"><label className="label">Event name</label><input className="input" value={f.name} onChange={(x) => setF({ ...f, name: x.target.value })} /></div>
        <div><label className="label">Venue</label><input className="input" value={f.venue} onChange={(x) => setF({ ...f, venue: x.target.value })} /></div>
        <div><label className="label">Category</label><select className="input" value={f.category} onChange={(x) => setF({ ...f, category: x.target.value })}>{["college", "wedding", "festival", "corporate", "community", "sports", "exhibition"].map((c) => <option key={c}>{c}</option>)}</select></div>
        <div><label className="label">Starts</label><input type="datetime-local" className="input" value={f.starts_at} onChange={(x) => setF({ ...f, starts_at: x.target.value })} /></div>
        <div><label className="label">Duration (h)</label><input type="number" className="input" value={f.duration_h} onChange={(x) => setF({ ...f, duration_h: x.target.value })} /></div>
        <div><label className="label">Expected attendance</label><input type="number" className="input" value={f.expected_attendance} onChange={(x) => setF({ ...f, expected_attendance: x.target.value })} /></div>
        <div><label className="label">Food</label><select className="input" value={f.food} onChange={(x) => setF({ ...f, food: x.target.value })}>{["none", "packaged", "catered", "stalls"].map((c) => <option key={c}>{c}</option>)}</select></div>
        <div><label className="label">Volunteers available</label><input type="number" className="input" value={f.volunteers_available} onChange={(x) => setF({ ...f, volunteers_available: x.target.value })} /></div>
        <div><label className="label">Sponsor requirements</label><input className="input" value={f.sponsor_requirements} onChange={(x) => setF({ ...f, sponsor_requirements: x.target.value })} /></div>
        <div className="sm:col-span-2 flex justify-end gap-2"><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={!f.name || !f.starts_at || a.busy} onClick={create}>Create & generate plan</button></div></div></Modal>
    </Page>
  );
}
