import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Empty, Load, Notice, Page, StatusPill, useAction, useLoad, when, ErrorBox, Pill } from "../components/ui";

export default function Pickups() {
  const { user } = useAuth();
  const subs = useLoad("/submissions");
  const cols = useLoad("/collections");
  const a = useAction();
  const [slot, setSlot] = useState("");
  const [msg, setMsg] = useState<any>(null);
  const schedule = (id: number) => a.run(async () => { const r = await api.post(`/submissions/${id}/schedule`, { slot: slot || null }); setMsg(r); subs.reload(); cols.reload(); });
  const cancel = (id: number) => a.run(async () => { await api.post(`/collections/${id}/cancel`); cols.reload(); subs.reload(); });
  return (
    <Page title="Pickups" subtitle="Schedule doorstep pickup for verified items. A trained collector confirms your household ID and weight — that’s what makes points spendable.">
      <Notice>Show your household ID to the collector: <b>{user.household_code}</b>. Weights are confirmed by the collector (scale or manual entry) — your estimate alone never decides rewards.</Notice>
      {a.err && <ErrorBox error={a.err} />}
      {msg && <Notice t={msg.run_status === "completed" ? "green" : "amber"}>{msg.summary}{msg.reason ? ` — ${msg.reason}` : ""} <Link className="underline" to={`/agents?run=${msg.run_id}`}>Agent trace</Link></Notice>}
      <div className="card">
        <h2 className="font-bold mb-2">Ready to schedule</h2>
        <Load state={subs}>{(rows: any[]) => {
          const ready = rows.filter((r) => !r.collection_id || ["cancelled", "failed"].includes(r.collection_status));
          return ready.length === 0 ? <Empty title="Nothing waiting" hint="Submit an item from the AI Waste Doctor first." /> : (
            <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Item</th><th className="th">Stream</th><th className="th">Weight</th><th className="th">Status</th><th className="th"></th></tr></thead><tbody>
              {ready.map((r) => <tr key={r.id}><td className="td">{r.detected_object}</td><td className="td">{r.stream}</td><td className="td">{r.est_weight_kg} kg</td><td className="td"><StatusPill s={r.status} />{r.flags?.length > 0 && <div className="text-xs text-coral">{r.flags[0].detail || r.flags[0].code}</div>}</td><td className="td"><button className="btn-primary btn-sm" disabled={a.busy || r.status === "flagged"} onClick={() => schedule(r.id)}>Schedule pickup</button></td></tr>)}
            </tbody></table></div>
          );
        }}</Load>
      </div>
      <div className="card">
        <h2 className="font-bold mb-2">My pickups</h2>
        <Load state={cols} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => (
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">#</th><th className="th">Item</th><th className="th">Scheduled</th><th className="th">Collector</th><th className="th">Weight</th><th className="th">Status</th><th className="th">Passport</th><th className="th"></th></tr></thead><tbody>
            {rows.map((c) => <tr key={c.id}><td className="td">{c.id}</td><td className="td">{c.detected_object || c.stream}</td><td className="td">{when(c.scheduled_for)}</td><td className="td">{c.worker_code || "—"}</td><td className="td">{c.verified_weight_kg ? `${c.verified_weight_kg} kg ✔` : `~${c.est_weight_kg} kg`}</td><td className="td"><StatusPill s={c.status} /></td><td className="td">{c.passport ? <Link className="underline text-deep" to={`/passports?ref=${c.passport}`}>{c.passport}</Link> : "—"}</td><td className="td">{["requested", "assigned", "accepted"].includes(c.status) && <button className="btn-secondary btn-sm" onClick={() => cancel(c.id)}>Cancel</button>}</td></tr>)}
          </tbody></table></div>
        )}</Load>
      </div>
    </Page>
  );
}
