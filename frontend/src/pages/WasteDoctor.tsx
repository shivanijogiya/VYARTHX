import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Camera, Upload, ShieldAlert, HelpCircle, CheckCircle2 } from "lucide-react";
import { api, fd } from "../api";
import { useAuth } from "../auth";
import { ErrorBox, Notice, Page, Pill, Spinner, useAction, useLoad, StatusPill } from "../components/ui";

export default function WasteDoctor() {
  const { user } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [text, setText] = useState("");
  const [kg, setKg] = useState("0.5");
  const [res, setRes] = useState<any>(null);
  const [sub, setSub] = useState<any>(null);
  const a = useAction();
  const ex = useLoad("/waste/examples");
  const ref = useRef<HTMLInputElement>(null);
  const canSubmit = ["citizen", "organiser"].includes(user.role);
  const pick = (f?: File | null) => { if (!f) return; setFile(f); setPreview(URL.createObjectURL(f)); };
  const analyse = () => a.run(async () => { setSub(null); setRes(await api.form("/waste/classify", fd({ image: file, text }))); });
  const submit = () => a.run(async () => setSub(await api.form("/submissions", fd({ image: file, text: text || res?.classification?.detected_object, est_weight_kg: kg }))));
  const c = res?.classification;
  return (
    <Page title="AI Waste Doctor" subtitle="Upload a photo or describe an item. VYARTHX tells you how to segregate and dispose of it — and asks for clarification when it isn’t sure.">
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card space-y-3">
          <div onClick={() => ref.current?.click()} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files[0]); }} className="border-2 border-dashed border-fresh/50 rounded-xl min-h-[11rem] grid place-items-center cursor-pointer hover:bg-mint/40 text-center p-3" role="button" tabIndex={0} aria-label="Upload photo" onKeyDown={(e) => e.key === "Enter" && ref.current?.click()}>
            {preview ? <img src={preview} alt="Selected waste" className="max-h-56 rounded-lg" /> : <div className="text-ink/60"><Camera className="mx-auto mb-1" /><div className="font-semibold">Tap to take or upload a photo</div><div className="text-xs">JPEG/PNG up to 8 MB — optional</div></div>}
          </div>
          <input ref={ref} type="file" accept="image/*" capture="environment" hidden onChange={(e) => pick(e.target.files?.[0])} />
          <div><label className="label" htmlFor="t">Describe the item (helps when the photo is unclear)</label><input id="t" className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. empty plastic water bottle with oil residue" /></div>
          <div className="flex flex-wrap gap-1">{ex.data?.slice(0, 8).map((e: any) => <button key={e.id} className="text-xs rounded-full bg-gray-100 hover:bg-mint px-2 py-1" onClick={() => setText(e.sample_text)}>{e.name}</button>)}</div>
          <div className="flex gap-2"><button className="btn-primary flex-1" disabled={a.busy || (!file && !text.trim())} onClick={analyse}><Upload size={16} />{a.busy ? "Analysing…" : "Analyse item"}</button>{file && <button className="btn-secondary" onClick={() => { setFile(null); setPreview(""); }}>Clear</button>}</div>
          {a.err && <ErrorBox error={a.err} />}
        </div>
        <div className="space-y-3">
          {a.busy && !res && <Spinner label="Agents are working…" />}
          {!res && !a.busy && <div className="card text-sm text-ink/70"><b>How it works:</b> the Segregation Agent runs an on-device image model plus the local waste knowledge base, applies safety rules for hazardous items, and only then recommends handling. Hazardous items are <b>never declared safe</b>. <div className="mt-2"><Pill t="amber">Note</Pill> The bundled image model is a generic ImageNet classifier (not trained on waste). Text hints and the knowledge base improve results; low confidence always triggers a clarification.</div></div>}
          {c && (
            <div className="card space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div><div className="text-xs text-ink/50">Detected</div><div className="text-xl font-extrabold text-forest">{c.detected_object || "Unknown"}</div></div>
                <div className="text-right"><div className="text-xs text-ink/50">Confidence</div><div className="text-xl font-bold">{Math.round((c.confidence || 0) * 100)}%</div></div>
              </div>
              <div className="flex flex-wrap gap-2"><Pill t={c.stream === "wet" ? "green" : c.stream === "dry" ? "blue" : c.stream === "special" ? "red" : "gray"}>{c.stream} stream</Pill>{c.material && <Pill>{c.material}</Pill>}{c.contamination && c.contamination !== "none" && <Pill t="amber">contamination: {c.contamination}</Pill>}<Pill t="gray">{c.mode}</Pill></div>
              {c.needs_clarification && <Notice t="amber" icon={<HelpCircle size={16} className="mt-0.5" />}><b>I’m not sure.</b> {c.reasoning} Please add a short description or a clearer photo. Top guesses: {(c.candidates || []).slice(0, 3).map((x: any) => `${x.name} (${Math.round(x.score * 100)}%)`).join(", ")}</Notice>}
              {c.hazard && <Notice t="red" icon={<ShieldAlert size={16} className="mt-0.5" />}><b>Special-care item.</b> Do not put in wet/dry bins. VYARTHX cannot declare hazardous waste safe — use an authorised channel. {c.handling}</Notice>}
              {!c.needs_clarification && <>
                <div><div className="font-semibold text-sm">What to do</div><p className="text-sm text-ink/80">{c.handling}</p><p className="text-sm text-ink/80 mt-1"><b>Disposal:</b> {c.disposal}</p></div>
                {c.contamination_warning && <Notice t="amber">{c.contamination_warning}</Notice>}
                {res.guidance?.length > 0 && <div><div className="font-semibold text-sm">Local guidance</div><ul className="list-disc pl-5 text-sm text-ink/80">{res.guidance.map((g: any, i: number) => <li key={i}>{g.text || g.title || String(g)}</li>)}</ul></div>}
                {res.destinations?.length > 0 && <div><div className="font-semibold text-sm">Nearest authorised destinations <span className="text-[10px] font-normal text-ink/50">(simulated placements)</span></div><ul className="text-sm text-ink/80">{res.destinations.slice(0, 3).map((d: any) => <li key={d.id || d.name}>{d.name} · {d.distance_km} km{d.type ? ` · ${d.type}` : ""}</li>)}</ul></div>}
                <div className="text-xs text-ink/50">{c.reward_note}</div>
              </>}
              <Link to={`/agents?run=${res.run_id}`} className="text-xs underline text-deep">View agent trace #{res.run_id}</Link>
              {canSubmit && !c.needs_clarification && !c.hazard && c.reward_eligible !== false && (
                <div className="border-t pt-3 flex flex-wrap items-end gap-2">
                  <div><label className="label" htmlFor="kg">Estimated weight (kg)</label><input id="kg" type="number" min="0.05" max="100" step="0.1" className="input w-28" value={kg} onChange={(e) => setKg(e.target.value)} /></div>
                  <button className="btn-primary" disabled={a.busy || !!sub} onClick={submit}><CheckCircle2 size={16} />Submit for verification</button>
                </div>
              )}
              {canSubmit && c.hazard && <Link to="/special" className="btn-secondary">Open special-care handover</Link>}
            </div>
          )}
          {sub && (
            <div className="card">
              <div className="flex items-center justify-between"><h3 className="font-bold">Submission #{sub.submission_id}</h3><StatusPill s={sub.run_status} /></div>
              <p className="text-sm mt-1">{sub.summary}</p>
              {sub.reward?.credited ? <div className="mt-2 text-sm"><Pill t="green">+{sub.reward.credited} provisional points</Pill> <span className="text-ink/60">Becomes spendable after the collector verifies your handover.</span></div> : <div className="mt-2 text-sm text-ink/60">{sub.reason || "No points credited for this submission."}</div>}
              {sub.verification?.flags?.length > 0 && <Notice t="amber">Verification flags: {sub.verification.flags.map((f: any) => f.detail).join("; ")}</Notice>}
              <div className="mt-3 flex gap-2"><Link to="/pickups" className="btn-primary">Schedule pickup</Link><Link to="/wallet" className="btn-secondary">Wallet</Link></div>
            </div>
          )}
        </div>
      </div>
    </Page>
  );
}
