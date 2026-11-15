import { useState } from "react";
import { api, fd } from "../api";
import { useAuth } from "../auth";
import MapView from "../components/MapView";
import { Empty, ErrorBox, Load, Modal, Notice, Page, Pill, StatusPill, Tabs, useAction, useLoad, when } from "../components/ui";

const COL: any = { new: "#F97373", verified: "#F59E0B", pending: "#1D4ED8", resolved: "#22C55E" };
export default function Hotspots() {
  const { user, meta } = useAuth();
  const isMun = user.role === "municipal";
  const [filt, setFilt] = useState({ ward_id: "", status: "", category: "" });
  const q = new URLSearchParams(Object.entries(filt).filter(([, v]) => v) as any).toString();
  const hs = useLoad(`/hotspots${q ? "?" + q : ""}`);
  const cl = useLoad(`/complaints?mine=${!isMun}`);
  const [tab, setTab] = useState("map");
  const [f, setF] = useState<any>({ description: "", ward: user.ward_id || "", lat: "", lng: "" });
  const [img, setImg] = useState<File | null>(null);
  const [res, setRes] = useState<any>(null);
  const [act, setAct] = useState<any>(null);
  const [note, setNote] = useState({ note: "", evidence: "" });
  const a = useAction();
  const submit = () => a.run(async () => {
    const w = meta.wards.find((x: any) => x.id === Number(f.ward));
    const r = await api.form("/complaints", fd({ description: f.description, image: img, lat: f.lat || w?.lat || 13.0827, lng: f.lng || w?.lng || 80.2707, source: img ? "image" : "text" }));
    setRes(r); setF({ ...f, description: "" }); setImg(null); hs.reload(); cl.reload();
  });
  const locate = () => navigator.geolocation?.getCurrentPosition((p) => setF((s: any) => ({ ...s, lat: p.coords.latitude, lng: p.coords.longitude })), () => alert("Location permission denied — choose a ward instead."));
  const doAct = (id: number, action: string, extra: any = {}) => a.run(async () => { const r = await api.post(`/complaints/${id}/action`, { action, ...extra }); setAct(null); if (r.approval_id) setRes({ summary: r.note }); cl.reload(); hs.reload(); });
  return (
    <Page title="Citizen Reporting & Hotspot Map" subtitle="Report overflowing bins, dumping or missed collection. Reports are classified, de-duplicated and prioritised — and only closed with evidence.">
      <Tabs value={tab} onChange={setTab} tabs={[["map", "Hotspot map"], ["report", "Report a problem"], ["list", isMun ? "All reports" : "My reports"]]} />
      {a.err && <ErrorBox error={a.err} />}
      {tab === "map" && <Load state={hs}>{(d: any) => (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center">
            <select className="input w-44" aria-label="Ward" value={filt.ward_id} onChange={(e) => setFilt({ ...filt, ward_id: e.target.value })}><option value="">All wards</option>{meta.wards.map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
            <select className="input w-44" aria-label="Category" value={filt.category} onChange={(e) => setFilt({ ...filt, category: e.target.value })}><option value="">All categories</option>{d.categories.map((c: string) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}</select>
            <select className="input w-40" aria-label="Status" value={filt.status} onChange={(e) => setFilt({ ...filt, status: e.target.value })}><option value="">Any status</option>{["submitted", "ai_classified", "assigned", "in_progress", "resolution_submitted", "closed", "reopened"].map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</select>
            <div className="flex gap-2 text-xs ml-auto">{Object.entries(COL).map(([k, c]) => <span key={k} className="flex items-center gap-1"><span className="w-3 h-3 rounded-full" style={{ background: c as string }} />{k}</span>)}</div>
          </div>
          <MapView markers={d.items.map((i: any) => ({ lat: i.lat, lng: i.lng, color: COL[i.map_class], radius: 5 + Math.min(i.repeat_count, 5), label: `<b>${i.category.replace(/_/g, " ")}</b><br/>${i.ward || ""} · ${i.status}<br/>${i.description}` }))} height={440} />
          <div className="text-xs text-ink/60">{d.items.length} reports shown · {d.repeat_hotspots.length} repeat hotspot clusters. Locations are approximate; demo reports are simulated.</div>
          {d.repeat_hotspots.length > 0 && <div className="card"><h3 className="font-bold mb-2">Repeat hotspots</h3>{d.repeat_hotspots.slice(0, 6).map((h: any, i: number) => <div key={i} className="text-sm py-1 border-b last:border-0">{h.count} reports · {h.open} open · {h.categories.join(", ").replace(/_/g, " ")} <span className="text-xs text-ink/50">({h.lat.toFixed(3)}, {h.lng.toFixed(3)})</span></div>)}</div>}
        </div>
      )}</Load>}
      {tab === "report" && (
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="card space-y-3">
            <div><label className="label" htmlFor="d">What’s the problem?</label><textarea id="d" rows={4} className="input" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} placeholder="e.g. Garbage overflowing near the market bin for 3 days" /></div>
            <div><label className="label" htmlFor="im">Photo (optional)</label><input id="im" type="file" accept="image/*" capture="environment" onChange={(e) => setImg(e.target.files?.[0] || null)} className="text-sm" /></div>
            <div className="grid grid-cols-2 gap-3"><div><label className="label" htmlFor="wd">Ward</label><select id="wd" className="input" value={f.ward} onChange={(e) => setF({ ...f, ward: e.target.value, lat: "", lng: "" })}>{meta.wards.map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></div><div className="flex items-end"><button className="btn-secondary w-full" onClick={locate}>Use my location</button></div></div>
            {f.lat && <div className="text-xs text-ink/60">Using GPS: {Number(f.lat).toFixed(4)}, {Number(f.lng).toFixed(4)}</div>}
            <button className="btn-primary w-full" disabled={a.busy || (!f.description.trim() && !img)} onClick={submit}>{a.busy ? "Submitting…" : "Submit report"}</button>
          </div>
          <div className="card">{!res ? <Empty title="No report submitted" hint="The Reporting, Verification and Municipal agents will process it." /> : (<div className="space-y-2 text-sm"><Notice t="green">{res.summary}</Notice>{res.complaint && <div>Category: <Pill t="blue">{res.complaint.category?.replace(/_/g, " ")}</Pill> Priority <b>P{res.complaint.priority}</b> {res.complaint.repeat_count > 1 && <Pill t="amber">merged with {res.complaint.repeat_count - 1} similar report(s)</Pill>}</div>}</div>)}</div>
        </div>
      )}
      {tab === "list" && <div className="card"><Load state={cl} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => (
        <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">#</th><th className="th">Category</th><th className="th">Ward</th><th className="th">Description</th><th className="th">Priority</th><th className="th">Status</th><th className="th">When</th><th className="th"></th></tr></thead><tbody>
          {rows.map((c) => <tr key={c.id}><td className="td">{c.id}</td><td className="td">{c.category?.replace(/_/g, " ")}</td><td className="td">{c.ward}</td><td className="td max-w-xs">{c.description.slice(0, 90)}</td><td className="td">P{c.priority}</td><td className="td"><StatusPill s={c.status} /></td><td className="td text-xs">{when(c.created_at)}</td>
            <td className="td whitespace-nowrap">{isMun && ["submitted", "ai_classified", "reopened"].includes(c.status) && <button className="btn-secondary btn-sm" onClick={() => doAct(c.id, "assign", { assignee: "ward sanitation team" })}>Assign</button>}{isMun && ["assigned", "in_progress", "reopened"].includes(c.status) && <button className="btn-primary btn-sm ml-1" onClick={() => setAct(c)}>Resolve</button>}{isMun && c.status === "resolution_submitted" && <button className="btn-blue btn-sm" onClick={() => doAct(c.id, "close")}>Close</button>}{!isMun && c.status === "resolution_submitted" && <><button className="btn-primary btn-sm" onClick={() => doAct(c.id, "confirm")}>Confirm fixed</button><button className="btn-secondary btn-sm ml-1" onClick={() => doAct(c.id, "reopen", { note: "Still not fixed" })}>Reopen</button></>}</td></tr>)}
        </tbody></table></div>)}</Load></div>}
      <Modal open={!!act} onClose={() => setAct(null)} title={`Resolve complaint #${act?.id}`}><div className="space-y-3"><Notice t="amber">A photo alone does not resolve a complaint. Add a resolution note and an evidence reference (e.g. work-order or photo ID).</Notice><div><label className="label">Resolution note (min 10 chars)</label><textarea className="input" value={note.note} onChange={(e) => setNote({ ...note, note: e.target.value })} /></div><div><label className="label">Evidence reference</label><input className="input" value={note.evidence} onChange={(e) => setNote({ ...note, evidence: e.target.value })} /></div><div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setAct(null)}>Cancel</button><button className="btn-primary" disabled={a.busy} onClick={() => doAct(act.id, "resolve", note)}>Submit resolution</button></div></div></Modal>
    </Page>
  );
}
