import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Empty, ErrorBox, Load, Modal, Notice, Page, Pill, StatusPill, Tabs, useAction, useLoad } from "../components/ui";

const CATS = ["", "furniture", "clothing", "books", "electronics_working", "appliances", "toys", "utensils", "bicycles", "other"];
export default function Reuse() {
  const { user } = useAuth();
  const [cat, setCat] = useState("");
  const [mine, setMine] = useState(false);
  const list = useLoad(`/reuse/listings?mine=${mine}${cat ? `&category=${cat}` : ""}`);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<any>({ title: "", description: "", mode: "giveaway", quantity: 1, price_inr: "" });
  const [created, setCreated] = useState<any>(null);
  const [ideas, setIdeas] = useState<any>(null);
  const a = useAction();
  const create = () => a.run(async () => { const r = await api.post("/reuse/listings", { ...f, quantity: Number(f.quantity), price_inr: f.price_inr === "" ? null : Number(f.price_inr), ward_id: user.ward_id }); setCreated(r); setOpen(false); list.reload(); });
  const transfer = (id: number) => { const who = prompt("Recipient name / organisation?"); if (who) a.run(async () => { await api.post(`/reuse/listings/${id}/transfer`, { recipient: who, quantity: 1 }); list.reload(); }); };
  const showIdeas = (c: string) => a.run(async () => setIdeas(await api.get(`/reuse/upcycling?category=${c}`)));
  return (
    <Page title="Reuse & Upcycling Exchange" subtitle="Give items a second life before they become waste: sell, donate, exchange or repair — with AI suggestions for category, likely recipients and upcycling ideas."
      actions={<button className="btn-primary" onClick={() => setOpen(true)}>+ List an item</button>}>
      {a.err && <ErrorBox error={a.err} />}
      {created && <Notice t="green">Listed <b>{created.listing.title}</b> as <b>{created.listing.category}</b> ({created.listing.condition}). {created.ai?.matches?.length ? `Possible recipients: ${created.ai.matches.map((m: any) => m.name).join(", ")}.` : ""} <button className="underline" onClick={() => showIdeas(created.listing.category)}>See upcycling ideas</button></Notice>}
      <div className="flex flex-wrap items-center gap-2"><select className="input w-48" value={cat} aria-label="Category" onChange={(e) => setCat(e.target.value)}>{CATS.map((c) => <option key={c} value={c}>{c || "All categories"}</option>)}</select><label className="text-sm flex items-center gap-1"><input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />My listings</label></div>
      <Load state={list} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">{rows.map((r) => (
          <div key={r.id} className="card">
            <div className="flex justify-between gap-2"><h3 className="font-bold">{r.title}</h3><StatusPill s={r.status} /></div>
            <div className="flex flex-wrap gap-1 mt-1"><Pill t="green">{r.category}</Pill><Pill t="blue">{r.mode}</Pill><Pill>{r.condition}</Pill>{r.price_inr != null && <Pill t="amber">₹{r.price_inr}</Pill>}</div>
            <p className="text-sm text-ink/70 mt-2">{r.description || "No description"}</p>
            <div className="text-xs text-ink/50 mt-2">{r.owner} · {r.ward} · qty {r.quantity}</div>
            {r.ai?.recipients?.length > 0 && <div className="text-xs mt-1 text-ink/70">Suggested: {r.ai.recipients.slice(0, 2).map((m: any) => m.name).join(", ")}</div>}
            <div className="mt-3 flex gap-2"><button className="btn-secondary btn-sm" onClick={() => showIdeas(r.category)}>Upcycle ideas</button>{r.user_id === user.id && r.status !== "transferred" && <button className="btn-primary btn-sm" onClick={() => transfer(r.id)}>Mark transferred</button>}</div>
          </div>))}</div>
      )}</Load>
      <Modal open={open} onClose={() => setOpen(false)} title="List an item">
        <div className="space-y-3">
          <div><label className="label">Title</label><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. School uniform set, size 10" /></div>
          <div><label className="label">Description</label><textarea className="input" rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></div>
          <div className="grid grid-cols-3 gap-3"><div><label className="label">Mode</label><select className="input" value={f.mode} onChange={(e) => setF({ ...f, mode: e.target.value })}>{["giveaway", "donate", "sell", "exchange", "repair"].map((m) => <option key={m}>{m}</option>)}</select></div><div><label className="label">Qty</label><input type="number" min={1} className="input" value={f.quantity} onChange={(e) => setF({ ...f, quantity: e.target.value })} /></div><div><label className="label">Price ₹</label><input type="number" min={0} className="input" disabled={f.mode !== "sell"} value={f.price_inr} onChange={(e) => setF({ ...f, price_inr: e.target.value })} /></div></div>
          {a.err && <ErrorBox error={a.err} />}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={a.busy || f.title.length < 3} onClick={create}>Publish</button></div>
        </div>
      </Modal>
      <Modal open={!!ideas} onClose={() => setIdeas(null)} title={`Upcycling ideas · ${ideas?.category}`}>{ideas && <><ul className="list-disc pl-5 text-sm space-y-1">{ideas.ideas.map((i: string, k: number) => <li key={k}>{i}</li>)}</ul><div className="text-xs text-ink/50 mt-3">{ideas.label}</div></>}</Modal>
    </Page>
  );
}
