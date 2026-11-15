import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowRight, Bot, ShieldCheck, User as UserIcon, Cog, RotateCw } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Empty, ErrorBox, Load, Notice, Page, Pill, Spinner, Stat, StatusPill, Tabs, useAction, useLoad, when } from "../components/ui";

function Trace({ id }: { id: number }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<any>(null);
  const { user } = useAuth();
  const a = useAction();
  const load = () => api.get(`/agents/runs/${id}`).then(setD).catch(setErr);
  useEffect(() => { setD(null); setErr(null); load(); }, [id]);
  const decide = (aid: number, ok: boolean) => a.run(async () => { await api.post(`/approvals/${aid}/decide`, { approve: ok, note: "" }); load(); });
  if (err) return <ErrorBox error={err} />;
  if (!d) return <Spinner />;
  const icon = (t: string) => t === "human" ? <UserIcon size={14} /> : t === "orchestrator" ? <Cog size={14} /> : <Bot size={14} />;
  return (
    <div className="card space-y-3">
      <div className="flex flex-wrap justify-between gap-2"><div><h2 className="font-bold text-lg">Run #{d.id} · {d.title}</h2><div className="text-xs text-ink/60">{d.workflow} · by {d.user} · {when(d.started_at)} · mode: {d.mode}</div></div><StatusPill s={d.status} /></div>
      <div className="text-sm text-ink/80">{d.summary}</div>
      {d.approvals?.map((x: any) => <div key={x.id} className="rounded-lg border border-amber/50 bg-amber/10 p-3 flex flex-wrap items-center justify-between gap-2 text-sm"><div><b>Approval gate:</b> {x.title} <StatusPill s={x.status} />{x.decision_note && <div className="text-xs">{x.decision_note}</div>}</div>{x.status === "pending" && ["municipal", x.required_role].includes(user.role) && <div className="flex gap-2"><button className="btn-primary btn-sm" disabled={a.busy} onClick={() => decide(x.id, true)}>Approve</button><button className="btn-danger btn-sm" disabled={a.busy} onClick={() => decide(x.id, false)}>Reject</button></div>}</div>)}
      {a.err && <ErrorBox error={a.err} />}
      <ol className="space-y-2">
        {d.steps.map((s: any) => (
          <li key={s.id} className="rounded-lg border p-3">
            <div className="flex flex-wrap items-center gap-2 text-sm"><span className="font-mono text-[11px] text-ink/40">{s.seq}</span><span className="flex items-center gap-1 font-bold text-forest">{icon(s.actor_type)}{s.agent}</span><Pill t="blue">{s.tool || "—"}</Pill><StatusPill s={s.status} />{s.approval_status !== "not_required" && <Pill t="amber">approval: {s.approval_status}</Pill>}{s.retries > 0 && <Pill t="amber"><RotateCw size={10} className="inline" /> {s.retries} retr{s.retries > 1 ? "ies" : "y"}</Pill>}<span className="text-[11px] text-ink/40 ml-auto">{s.duration_ms} ms</span></div>
            <div className="text-sm mt-1">{s.task}</div>
            {s.error && <div className="text-xs text-coral mt-1">{s.error}</div>}
            {s.next_agent && <div className="text-xs text-ink/50 mt-1 flex items-center gap-1"><ArrowRight size={12} />hands over to <b>{s.next_agent}</b></div>}
            <details className="mt-1"><summary className="text-xs text-deep cursor-pointer">Inputs / outputs</summary><pre className="text-[11px] bg-cream rounded p-2 overflow-auto max-h-56">{JSON.stringify({ input: s.input, output: s.output }, null, 2)}</pre></details>
          </li>))}
      </ol>
    </div>
  );
}

export default function AgentCentre() {
  const { user } = useAuth();
  const [sp, setSp] = useSearchParams();
  const sel = sp.get("run") ? Number(sp.get("run")) : null;
  const [tab, setTab] = useState("runs");
  const [flt, setFlt] = useState({ status: "", workflow: "" });
  const q = new URLSearchParams(Object.entries(flt).filter(([, v]) => v) as any).toString();
  const runs = useLoad(`/agents/runs${q ? "?" + q : ""}`);
  const info = useLoad("/agents");
  const stats = useLoad(user.role === "municipal" ? "/agents/stats" : null);
  const aud = useLoad(user.role === "municipal" && tab === "audit" ? "/audit?limit=120" : null, [tab]);
  return (
    <Page title="AI Agent Activity Centre" subtitle="See what every agent did, which tool it called, who it handed over to, where retries happened and where a human had to approve.">
      <Load state={info}>{(d: any) => <Notice>Orchestration engine: <b>{d.engine}</b> · mode: <b>{d.mode === "deterministic" ? "deterministic local demo mode (no paid API key needed)" : "LLM-assisted phrasing"}</b>. {d.guardrails.join(" ")}</Notice>}</Load>
      {user.role === "municipal" && stats.data && <div className="grid grid-cols-2 lg:grid-cols-5 gap-3"><Stat label="Workflow runs" value={Object.values(stats.data.runs_by_status).reduce((s: any, v: any) => s + v, 0) as number} /><Stat label="Agent steps" value={stats.data.total_steps} tone="blue" /><Stat label="Retries" value={stats.data.retries} tone="amber" /><Stat label="Failed steps" value={stats.data.failed_steps} tone="coral" /><Stat label="Pending approvals" value={stats.data.pending_approvals} tone="amber" /></div>}
      <Tabs value={tab} onChange={setTab} tabs={[["runs", "Workflow runs"], ["agents", "Agents & workflows"], ...(user.role === "municipal" ? [["audit", "Audit log"]] as [string, string][] : [])]} />
      {tab === "runs" && (
        <div className="grid xl:grid-cols-5 gap-4">
          <div className="xl:col-span-2 card max-h-[80vh] overflow-auto">
            <div className="flex gap-2 mb-2"><select className="input" aria-label="Status" value={flt.status} onChange={(e) => setFlt({ ...flt, status: e.target.value })}><option value="">Any status</option>{["completed", "awaiting_approval", "escalated", "rejected", "failed"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select><select className="input" aria-label="Workflow" value={flt.workflow} onChange={(e) => setFlt({ ...flt, workflow: e.target.value })}><option value="">Any workflow</option>{info.data?.workflows.map((w: any) => <option key={w.name} value={w.name}>{w.name}</option>)}</select></div>
            <Load state={runs} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => rows.map((r) => (
              <button key={r.id} onClick={() => setSp({ run: String(r.id) })} className={`w-full text-left rounded-lg border p-2.5 mb-2 hover:border-forest ${sel === r.id ? "border-forest bg-mint/40" : ""}`}>
                <div className="flex justify-between gap-2"><b className="text-sm">#{r.id} {r.title}</b><StatusPill s={r.status} /></div>
                <div className="text-xs text-ink/60">{r.workflow} · {r.step_count} steps · {r.agents.length} agents · {when(r.started_at)}</div>
                {r.pending_approvals > 0 && <Pill t="amber">awaiting approval</Pill>}
              </button>))}</Load>
          </div>
          <div className="xl:col-span-3">{sel ? <Trace id={sel} /> : <div className="card"><Empty title="Select a run" hint="Open a workflow run to see the agent-to-agent trace." /></div>}</div>
        </div>
      )}
      {tab === "agents" && <Load state={info}>{(d: any) => (<div className="grid lg:grid-cols-2 gap-4"><div className="card"><h3 className="font-bold mb-2">Agents</h3>{d.agents.map((x: any) => <div key={x.name} className="border-b last:border-0 py-2 text-sm"><div className="flex justify-between"><b className="text-forest">{x.name}</b><Pill t="gray">{x.steps_logged} steps logged</Pill></div><div className="text-ink/70">{x.role}</div></div>)}</div><div className="card"><h3 className="font-bold mb-2">Workflows (LangGraph)</h3>{d.workflows.map((w: any) => <div key={w.name} className="border-b last:border-0 py-2 text-sm"><b>{w.title}</b><div className="text-xs text-ink/60 flex flex-wrap items-center gap-1 mt-1">{w.agents.map((x: string, i: number) => <span key={i} className="flex items-center gap-1">{i > 0 && <ArrowRight size={11} />}{x}</span>)}</div></div>)}</div></div>)}</Load>}
      {tab === "audit" && <Load state={aud} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => <div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">When</th><th className="th">User</th><th className="th">Action</th><th className="th">Entity</th><th className="th">Detail</th></tr></thead><tbody>{rows.map((r) => <tr key={r.id}><td className="td whitespace-nowrap">{when(r.created_at)}</td><td className="td">{r.user_id ?? "system"}</td><td className="td font-mono text-xs">{r.action}</td><td className="td">{r.entity} {r.entity_id}</td><td className="td text-xs text-ink/60 max-w-xs truncate">{JSON.stringify(r.detail)}</td></tr>)}</tbody></table></div>}</Load>}
    </Page>
  );
}
