import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useAuth } from "../auth";
import { DataBadge, ErrorBox, Load, Notice, Page, Pill, Tabs, useAction, useLoad, fmt, Modal } from "../components/ui";

export default function Community() {
  const { user, refresh } = useAuth();
  const [tab, setTab] = useState("league");
  const [ctype, setCtype] = useState("");
  const lg = useLoad(`/league${ctype ? `?ctype=${ctype}` : ""}`);
  const ch = useLoad("/challenges");
  const bh = useLoad(["citizen", "organiser"].includes(user.role) ? "/behaviour" : null);
  const comms = useLoad("/communities");
  const a = useAction();
  const [open, setOpen] = useState(false);
  const [cf, setCf] = useState<any>({ title: "", description: "", rule: "verified_submissions", target: 5, points_reward: 25, days: 7 });
  const join = (id: number) => a.run(async () => { await api.post(`/challenges/${id}/join`); ch.reload(); });
  const joinCommunity = (id: number) => a.run(async () => { await api.put("/auth/me", { community_id: id }); await refresh(); lg.reload(); });
  const mk = () => a.run(async () => { await api.post("/challenges", { ...cf, target: Number(cf.target), points_reward: Number(cf.points_reward), days: Number(cf.days) }); setOpen(false); ch.reload(); });
  const setGoal = (n: number) => a.run(async () => { await api.put("/auth/me", { goals: { weekly_submissions: n } }); bh.reload(); });
  return (
    <Page title="Green Neighbourhood League" subtitle="Communities are ranked by waste QUALITY — segregation accuracy, participation, low contamination and verified handover — never by kilograms." badge={lg.data?.data_class}>
      <Tabs value={tab} onChange={setTab} tabs={[["league", "League"], ["challenges", "Challenges"], ...(["citizen", "organiser"].includes(user.role) ? [["me", "My behaviour & goals"]] as [string, string][] : [])]} />
      {a.err && <ErrorBox error={a.err} />}
      {tab === "league" && (
        <Load state={lg}>{(d: any) => (
          <>
            <Notice>{d.ranking_rule}</Notice>
            <div className="flex gap-2 items-center"><label className="label !mb-0" htmlFor="ct">Type</label><select id="ct" className="input w-44" value={ctype} onChange={(e) => setCtype(e.target.value)}><option value="">All</option>{["apartment", "college", "office", "ward", "school"].map((t) => <option key={t}>{t}</option>)}</select></div>
            <div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">#</th><th className="th">Community</th><th className="th">Type</th><th className="th">Quality score</th><th className="th">Segregation</th><th className="th">Participation</th><th className="th">Contamination</th><th className="th">Handover</th><th className="th"></th></tr></thead><tbody>
              {d.rows.map((r: any) => <tr key={r.id} className={user.community_id === r.id ? "bg-mint/40" : ""}><td className="td font-bold">{r.rank}</td><td className="td"><b>{r.name}</b><div className="text-[10px] text-ink/50">{r.basis}</div></td><td className="td">{r.type}</td><td className="td"><b>{fmt(r.score, 0)}</b></td><td className="td">{fmt(r.verified_segregation_pct, 0)}%</td><td className="td">{fmt(r.participation_pct, 0)}%</td><td className="td">{fmt(r.contamination_pct, 0)}%</td><td className="td">{fmt(r.correct_handover_pct, 0)}%</td><td className="td">{["citizen", "organiser"].includes(user.role) && user.community_id !== r.id && <button className="btn-secondary btn-sm" onClick={() => joinCommunity(r.id)}>Join</button>}{user.community_id === r.id && <Pill t="green">Mine</Pill>}</td></tr>)}
            </tbody></table></div>
            <div className="card"><h3 className="font-bold mb-2">Quality components</h3><div className="h-64"><ResponsiveContainer><BarChart data={d.rows.slice(0, 8)}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" fontSize={10} interval={0} tickFormatter={(v: string) => v.slice(0, 10)} /><YAxis fontSize={11} /><Tooltip /><Legend /><Bar dataKey="verified_segregation_pct" name="Segregation %" fill="#31A24C" /><Bar dataKey="participation_pct" name="Participation %" fill="#38BDF8" /><Bar dataKey="correct_handover_pct" name="Handover %" fill="#7B61FF" /></BarChart></ResponsiveContainer></div></div>
          </>
        )}</Load>
      )}
      {tab === "challenges" && (
        <>
          {["municipal", "organiser"].includes(user.role) && <div><button className="btn-primary" onClick={() => setOpen(true)}>+ Create challenge</button></div>}
          <Load state={ch} emptyIf={(d: any[]) => d.length === 0}>{(rows: any[]) => <div className="grid md:grid-cols-2 gap-3">{rows.map((c) => (
            <div key={c.id} className="card"><div className="flex justify-between"><h3 className="font-bold">{c.title}</h3><Pill t="blue">{c.points_reward} pts</Pill></div><p className="text-sm text-ink/70 mt-1">{c.description}</p><div className="text-xs text-ink/50 mt-1">{c.cadence} · target {c.target} · {c.participants} joined · rule: {c.rule.replace(/_/g, " ")}</div>
              {c.joined ? <div className="mt-2"><div className="h-2 bg-btn rounded-full"><div className="h-full bg-fresh rounded-full" style={{ width: `${Math.min(100, (c.progress / c.target) * 100)}%` }} /></div><div className="text-xs mt-1">{c.progress}/{c.target} {c.completed && <Pill t="green">completed</Pill>}</div></div> : user.role !== "municipal" && <button className="btn-primary btn-sm mt-2" onClick={() => join(c.id)}>Join</button>}
            </div>))}</div>}</Load>
        </>
      )}
      {tab === "me" && (
        <Load state={bh}>{(d: any) => (
          <div className="grid lg:grid-cols-3 gap-4">
            <div className="card lg:col-span-2"><h3 className="font-bold mb-2">Weekly progress</h3><div className="h-56"><ResponsiveContainer><BarChart data={d.progress}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="week" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Legend /><Bar dataKey="submissions" name="Submissions" fill="#0866FF" /><Bar dataKey="clean_pct" name="Clean %" fill="#31A24C" /></BarChart></ResponsiveContainer></div>
              <div className="mt-3 text-sm">Common issues: {Object.entries(d.issues).length ? Object.entries(d.issues).map(([k, v]) => <Pill key={k} t="amber">{k} ×{v as any}</Pill>) : "none 🎉"}</div></div>
            <div className="space-y-3">
              <div className="card"><h3 className="font-bold">Weekly goal</h3><div className="text-sm">{d.this_week}/{d.weekly_goal.weekly_submissions} submissions this week</div><div className="flex gap-1 mt-2">{[3, 5, 7, 10].map((n) => <button key={n} className={n === d.weekly_goal.weekly_submissions ? "btn-primary btn-sm" : "btn-secondary btn-sm"} onClick={() => setGoal(n)}>{n}</button>)}</div></div>
              <div className="card"><h3 className="font-bold mb-1">Nudges</h3>{d.nudges.map((n: any, i: number) => <div key={i} className="text-sm py-1 border-b last:border-0"><b>{n.title}</b><div className="text-ink/70">{n.body}</div></div>)}<div className="text-[11px] text-ink/50 mt-2">Limited to {d.notification_prefs.max_per_day}/day. Change in preferences.</div></div>
            </div>
          </div>
        )}</Load>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Create challenge"><div className="space-y-3">
        <div><label className="label">Title</label><input className="input" value={cf.title} onChange={(e) => setCf({ ...cf, title: e.target.value })} /></div>
        <div><label className="label">Description</label><textarea className="input" value={cf.description} onChange={(e) => setCf({ ...cf, description: e.target.value })} /></div>
        <div className="grid grid-cols-3 gap-3"><div><label className="label">Rule</label><select className="input" value={cf.rule} onChange={(e) => setCf({ ...cf, rule: e.target.value })}>{["verified_submissions", "clean_streak", "ewaste", "reuse", "compost"].map((r) => <option key={r}>{r}</option>)}</select></div><div><label className="label">Target</label><input type="number" className="input" value={cf.target} onChange={(e) => setCf({ ...cf, target: e.target.value })} /></div><div><label className="label">Days</label><input type="number" className="input" value={cf.days} onChange={(e) => setCf({ ...cf, days: e.target.value })} /></div></div>
        <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={!cf.title || a.busy} onClick={mk}>Create</button></div></div></Modal>
    </Page>
  );
}
