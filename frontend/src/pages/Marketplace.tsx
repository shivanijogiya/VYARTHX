import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { DataBadge, Empty, ErrorBox, Load, Modal, Notice, Page, Pill, StatusPill, Tabs, useAction, useLoad, fmt } from "../components/ui";

export default function Marketplace() {
  const { user, meta } = useAuth();
  const [tab, setTab] = useState("matches");
  const mats = useLoad("/marketplace/materials");
  const matches = useLoad("/marketplace/matches");
  const supply = useLoad("/marketplace/listings?kind=supply");
  const demand = useLoad("/marketplace/listings?kind=demand");
  const a = useAction();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<any>({ kind: user.role === "recycler" || user.role === "facility" ? "demand" : "supply", material_key: "pet_bottle", quantity_kg: 10, condition: "clean", contamination: "none", price_inr_per_kg: "" });
  const [note, setNote] = useState<any>(null);
  const reloadAll = () => { matches.reload(); supply.reload(); demand.reload(); };
  const create = () => a.run(async () => { const r = await api.post("/marketplace/listings", { ...f, quantity_kg: Number(f.quantity_kg), price_inr_per_kg: f.price_inr_per_kg === "" ? null : Number(f.price_inr_per_kg), ward_id: user.ward_id }); setOpen(false); setNote(`Listing #${r.listing.id} created — ${r.matches?.count ?? 0} new match(es) recommended.`); reloadAll(); });
  const request = (id: number) => a.run(async () => { const r = await api.post(`/marketplace/matches/${id}/request`); setNote(`${r.note} (approval #${r.approval_id})`); reloadAll(); });
  const sweep = () => a.run(async () => { const r = await api.post("/marketplace/recommend"); setNote(r.summary); reloadAll(); });
  const canPost = true;
  const listTable = (st: any, kind: string) => (
    <Load state={st} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => (
      <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Material</th><th className="th">Qty (kg)</th><th className="th">Condition</th><th className="th">Where</th><th className="th">{kind === "demand" ? "Buyer" : "Seller"}</th><th className="th">Indicative price</th><th className="th">Status</th></tr></thead><tbody>
        {rows.map((l) => <tr key={l.id}><td className="td">{l.title || l.material_key}</td><td className="td">{fmt(l.remaining_kg)}</td><td className="td">{l.condition}{l.contamination !== "none" && <Pill t="amber">{l.contamination}</Pill>}</td><td className="td">{l.ward}</td><td className="td">{l.facility || l.seller_type}</td><td className="td">{l.price_inr_per_kg != null ? `₹${l.price_inr_per_kg}/kg` : "—"}<div className="text-[10px] text-ink/40">{l.price_source}</div></td><td className="td"><StatusPill s={l.status} /> <DataBadge cls={l.data_class} /></td></tr>)}
      </tbody></table></div>
    )}</Load>
  );
  return (
    <Page title="Circular Marketplace" subtitle="Match clean recovered material with recycler demand. Prices are user-entered indicators, never live market rates. Transfers need human approval."
      actions={<><button className="btn-primary" onClick={() => setOpen(true)}>+ New listing</button>{["municipal", "recycler", "facility"].includes(user.role) && <button className="btn-secondary" onClick={sweep} disabled={a.busy}>Run matching agent</button>}</>}>
      {note && <Notice t="green">{note}</Notice>}
      {a.err && <ErrorBox error={a.err} />}
      <Tabs value={tab} onChange={setTab} tabs={[["matches", "Recommended matches"], ["supply", "Supply"], ["demand", "Recycler demand"]]} />
      <div className="card">
        {tab === "matches" && <Load state={matches} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => (
          <div className="grid md:grid-cols-2 gap-3">{rows.map((m) => (
            <div key={m.id} className="rounded-xl border p-3 text-sm">
              <div className="flex justify-between items-start"><div className="font-bold">{m.supply.title} → {m.demand.buyer}</div><Pill t="blue">score {Math.round(m.score * 100)}</Pill></div>
              <div className="text-xs text-ink/60 mt-1">{fmt(m.qty_kg)} kg · {fmt(m.distance_km)} km{m.demand.price_inr_per_kg != null ? ` · indicative ₹${m.demand.price_inr_per_kg}/kg` : ""}</div>
              {m.rationale?.reasons && <ul className="list-disc pl-4 mt-1 text-xs text-ink/70">{m.rationale.reasons.slice(0, 4).map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>}
              <div className="mt-2 flex items-center gap-2"><StatusPill s={m.status} />{m.status === "recommended" && <button className="btn-primary btn-sm" onClick={() => request(m.id)} disabled={a.busy}>Request transfer</button>}{m.status === "requested" && <Link to="/agents" className="text-xs underline text-deep">Awaiting approval</Link>}</div>
            </div>))}</div>
        )}</Load>}
        {tab === "supply" && listTable(supply, "supply")}
        {tab === "demand" && listTable(demand, "demand")}
      </div>
      <Notice t="amber">Only clean, recovered material with a Waste Passport should be listed. A match is a <b>recommendation</b> — VYARTHX does not move material or money. Data class for demo listings: <b>{meta?.record_class}</b>.</Notice>
      <Modal open={open} onClose={() => setOpen(false)} title="New listing">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Type</label><select className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="supply">Supply (I have material)</option>{["recycler", "facility", "municipal"].includes(user.role) && <option value="demand">Demand (I want material)</option>}</select></div>
            <div><label className="label">Material</label><select className="input" value={f.material_key} onChange={(e) => setF({ ...f, material_key: e.target.value })}>{mats.data?.map((m: any) => <option key={m.key} value={m.key}>{m.name}</option>)}</select></div>
            <div><label className="label">Quantity (kg)</label><input type="number" min="0.1" className="input" value={f.quantity_kg} onChange={(e) => setF({ ...f, quantity_kg: e.target.value })} /></div>
            <div><label className="label">Indicative price ₹/kg (optional)</label><input type="number" min="0" className="input" value={f.price_inr_per_kg} onChange={(e) => setF({ ...f, price_inr_per_kg: e.target.value })} /></div>
            <div><label className="label">Condition</label><select className="input" value={f.condition} onChange={(e) => setF({ ...f, condition: e.target.value })}><option>clean</option><option>rinsed</option><option>mixed</option><option>soiled</option></select></div>
            <div><label className="label">Contamination</label><select className="input" value={f.contamination} onChange={(e) => setF({ ...f, contamination: e.target.value })}><option>none</option><option>light</option><option>heavy</option></select></div>
          </div>
          {a.err && <ErrorBox error={a.err} />}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={a.busy} onClick={create}>Create & match</button></div>
        </div>
      </Modal>
    </Page>
  );
}
