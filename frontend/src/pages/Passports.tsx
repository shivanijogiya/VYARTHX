import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle2, Circle, Link2, ShieldCheck } from "lucide-react";
import { Empty, ErrorBox, Load, Notice, Page, Pill, StatusPill, Spinner, useLoad, when, fmt } from "../components/ui";
import { api } from "../api";

function Balance({ m }: { m: any }) {
  const parts = [["Recovered", m.recovered_kg, "#22C55E"], ["Rejects", m.rejects_kg, "#F59E0B"], ["Loss/moisture", m.process_loss_kg, "#38BDF8"], ["Other", m.other_output_kg, "#A78BFA"], ["Unaccounted", Math.max(m.discrepancy_kg, 0), "#F97373"]];
  const tot = m.input_kg || 1;
  return (
    <div>
      <div className="flex h-4 rounded-full overflow-hidden bg-gray-100">{parts.map(([l, v, c]: any) => v > 0 && <div key={l} title={`${l}: ${v} kg`} style={{ width: `${(v / tot) * 100}%`, background: c }} />)}</div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs">{parts.map(([l, v, c]: any) => <span key={l} className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />{l}: <b>{fmt(v, 2)} kg</b></span>)}</div>
      <div className="text-xs text-ink/60 mt-2">{m.equation}. {m.complete ? "Mass balance closes." : "Not yet complete — facility records are pending."}{m.discrepancy_flag && <b className="text-coral"> Discrepancy flagged.</b>}</div>
    </div>
  );
}

export default function Passports() {
  const [sp, setSp] = useSearchParams();
  const list = useLoad("/passports");
  const ref = sp.get("ref");
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<any>(null);
  useEffect(() => { if (!ref) { setD(null); return; } setErr(null); api.get(`/passports/${ref}`).then(setD).catch(setErr); }, [ref]);
  return (
    <Page title="Waste Passport" subtitle="A tamper-evident, hash-chained journey for every batch. Recovery is only counted from facility-confirmed quantities — we never claim that everything is recycled.">
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card lg:col-span-1 max-h-[75vh] overflow-auto">
          <h2 className="font-bold mb-2">Batches</h2>
          <Load state={list} emptyIf={(x: any[]) => x.length === 0}>{(rows: any[]) => rows.map((b) => (
            <button key={b.id} onClick={() => setSp({ ref: b.code })} className={`w-full text-left rounded-lg border p-2.5 mb-2 hover:border-forest ${ref === b.code ? "border-forest bg-mint/40" : ""}`}>
              <div className="flex justify-between items-center"><b className="text-sm">{b.code}</b><StatusPill s={b.status} /></div>
              <div className="text-xs text-ink/60">{b.input_kg} kg · {b.material_key || b.stream} · {b.ward}</div>
            </button>
          ))}</Load>
        </div>
        <div className="lg:col-span-2 space-y-4">
          {!ref && <div className="card"><Empty title="Select a batch" hint="Pick a passport to see its journey and mass balance." /></div>}
          {err && <ErrorBox error={err} />}
          {ref && !d && !err && <Spinner />}
          {d && (<>
            <div className="card">
              <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-lg font-extrabold text-forest">{d.code}</h2><div className="text-sm text-ink/60">{d.material_key || d.stream} · {d.input_kg} kg input · {d.ward}{d.owner ? ` · ${d.owner}` : ""}</div></div><div className="text-right"><StatusPill s={d.status} /><div className="text-xs text-ink/60 mt-1">{d.status_text}</div></div></div>
              <div className="mt-4"><Balance m={d.mass_balance} /></div>
              <div className="mt-3 flex items-center gap-2 text-xs"><Link2 size={14} />{d.chain.intact ? <Pill t="green">Hash chain intact · {d.chain.events} events · head {d.chain.head?.slice(0, 10)}…</Pill> : <Pill t="red">Chain broken — tampering suspected</Pill>}</div>
            </div>
            <div className="card">
              <h3 className="font-bold mb-3">Journey</h3>
              <ol className="relative border-l-2 border-mint ml-2 space-y-4">
                {d.events.map((e: any) => (
                  <li key={e.id} className="ml-4">
                    <span className="absolute -left-[9px] bg-white">{e.status === "confirmed" || e.status === "recorded" ? <CheckCircle2 size={16} className="text-fresh" /> : <Circle size={16} className="text-gray-400" />}</span>
                    <div className="flex flex-wrap items-center gap-2"><b className="text-sm">{e.event_type}</b><Pill t="blue">{e.stage}</Pill><span className="text-xs text-ink/50">{when(e.ts)}</span><code className="text-[10px] text-ink/40">#{e.hash}</code></div>
                    <div className="text-xs text-ink/70">{e.actor_name} ({e.actor_role}){e.location ? ` · ${e.location}` : ""}{e.weight_kg != null ? ` · ${e.weight_kg} kg` : ""}</div>
                    {e.evidence && <div className="text-xs text-ink/50">Evidence: {e.evidence}</div>}
                  </li>
                ))}
              </ol>
            </div>
            <Notice icon={<ShieldCheck size={16} className="mt-0.5" />}>{d.claim_rule}</Notice>
          </>)}
        </div>
      </div>
    </Page>
  );
}
