import { useState } from "react";
import { Link } from "react-router-dom";
import { PlayCircle, RotateCcw, CheckCircle2 } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { ErrorBox, Notice, Page, StatusPill, useAction } from "../components/ui";

const TOUR = [
  ["Citizen", "citizen@vyarthx.demo", "Open AI Waste Doctor → upload any photo or describe “old AA battery” → see hazard handling and the clarification gate."],
  ["Citizen", "citizen@vyarthx.demo", "Submit a clean dry item → schedule pickup → watch provisional points appear in the Wallet."],
  ["Worker", "worker@vyarthx.demo", "Accept the pickup → Confirm handover with the household code and weight → verified points + Waste Passport are created."],
  ["Facility", "facility@vyarthx.demo", "Confirm receipt and record processing. The mass balance must close; only then the final recovery bonus is credited."],
  ["Recycler", "recycler@vyarthx.demo", "See recommended supply matches; a transfer request creates an approval — no money or material moves."],
  ["Municipal", "municipal@vyarthx.demo", "Command Centre → Dynamic Collection (approve a route plan) → Digital Twin (run Scenario B or E) → AI Agent Centre trace."],
];
export default function DemoGuide() {
  const { user, meta } = useAuth();
  const a = useAction();
  const [res, setRes] = useState<any>(null);
  const [rst, setRst] = useState<any>(null);
  const run = () => a.run(async () => setRes(await api.post("/demo/run-story")));
  const reset = () => { if (confirm("Reset ALL sample data to the original seeded state? Your current session may need re-login.")) a.run(async () => { setRst(await api.post("/demo/reset")); }); };
  if (!meta?.demo_mode) return <Page title="Guided Demo" subtitle="Demo mode is disabled."><Notice t="amber">Set DEMO_MODE=true in .env to enable the guided demo.</Notice></Page>;
  return (
    <Page title="Guided Demo" subtitle="Run the whole story with real agent workflows, or follow the click-through below. All records are labelled simulated.">
      {a.err && <ErrorBox error={a.err} />}
      <div className="card flex flex-wrap items-center gap-3"><button className="btn-primary" onClick={run} disabled={a.busy}><PlayCircle size={16} />{a.busy ? "Running agents…" : "Run the end-to-end story"}</button>{user.role === "municipal" && <button className="btn-secondary" onClick={reset} disabled={a.busy}><RotateCcw size={16} />Reset sample data</button>}<span className="text-sm text-ink/60">Creates real workflow runs (citizen → agents → collector → facility → municipal → twin) you can open in the Agent Centre.</span></div>
      {rst && <Notice t="green">{rst.note}</Notice>}
      {res && <div className="card"><h3 className="font-bold mb-2">Story result</h3><ol className="space-y-2">{res.steps.map((s: any) => <li key={s.run_id} className="flex flex-wrap items-start gap-2 text-sm border-b last:border-0 pb-2"><CheckCircle2 size={16} className="text-fresh mt-0.5" /><div className="flex-1"><b>{s.title}</b><div className="text-xs text-ink/60">{s.summary}</div></div><StatusPill s={s.status} /><Link to={`/agents?run=${s.run_id}`} className="btn-secondary btn-sm">Trace</Link></li>)}</ol><div className="text-xs text-ink/50 mt-2">{res.note}</div></div>}
      <div className="card"><h3 className="font-bold mb-2">Click-through script</h3><ol className="list-decimal pl-5 space-y-2 text-sm">{TOUR.map(([role, email, text], i) => <li key={i}><b>{role}</b> <code className="text-xs bg-cream px-1 rounded">{email}</code> — {text}</li>)}</ol><div className="text-xs text-ink/60 mt-3">Sign out and use the one-click demo accounts on the login page to switch roles. Password for all: <code>Vyarthx@2026</code>.</div></div>
    </Page>
  );
}
