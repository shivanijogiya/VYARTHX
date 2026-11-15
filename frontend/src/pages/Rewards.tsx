import { useState } from "react";
import { api } from "../api";
import { ErrorBox, Load, Modal, Notice, Page, Pill, useAction, useLoad } from "../components/ui";

export default function Rewards() {
  const cat = useLoad("/rewards/catalog");
  const wal = useLoad("/wallet");
  const a = useAction();
  const [sel, setSel] = useState<any>(null);
  const [done, setDone] = useState<any>(null);
  const redeem = () => a.run(async () => { const r = await api.post("/rewards/redeem", { catalog_id: sel.id }); setDone(r); setSel(null); wal.reload(); });
  const spend = wal.data?.balances?.spendable ?? 0;
  return (
    <Page title="Reward Redemption Marketplace" subtitle={`Only verified and final points can be spent. You have ${spend} spendable points.`}>
      <Notice t="amber">Every reward here is a <b>demo voucher</b>. Nothing is issued by a real partner, and no real discount, fare concession or travel benefit is granted.</Notice>
      {done && <Notice t="green">Redeemed <b>{done.title}</b>. Voucher code <b>{done.redemption.voucher_code}</b>. {done.notice}</Notice>}
      <Load state={cat}>{(rows: any[]) => (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {rows.map((r) => (
            <div key={r.id} className="card flex flex-col">
              <div className="flex justify-between items-start gap-2"><h3 className="font-bold">{r.title}</h3><Pill t="blue">{r.points_cost} pts</Pill></div>
              <div className="text-xs text-ink/60 mt-0.5">{r.partner}</div>
              <p className="text-sm mt-2 flex-1">{r.scope}<span className="block text-xs text-ink/60 mt-1">Eligibility: {r.eligibility} · Integration: {r.integration_status}</span></p>
              {r.simulation_only && <div className="mt-2"><Pill t="purple">Proposed partnership — simulation only</Pill></div>}
              <button className="btn-primary mt-3" disabled={spend < r.points_cost} onClick={() => setSel(r)}>{spend < r.points_cost ? `Need ${r.points_cost - spend} more` : "Redeem"}</button>
            </div>
          ))}
        </div>
      )}</Load>
      <Modal open={!!sel} onClose={() => setSel(null)} title="Confirm redemption">
        {sel && <div className="space-y-3 text-sm"><p>Spend <b>{sel.points_cost}</b> points on <b>{sel.title}</b>?</p>{sel.simulation_only && <Notice t="amber">This is a proposal-stage partnership shown for simulation only. No real benefit will be issued.</Notice>}{a.err && <ErrorBox error={a.err} />}<div className="flex gap-2 justify-end"><button className="btn-secondary" onClick={() => setSel(null)}>Cancel</button><button className="btn-primary" disabled={a.busy} onClick={redeem}>Confirm</button></div></div>}
      </Modal>
    </Page>
  );
}
