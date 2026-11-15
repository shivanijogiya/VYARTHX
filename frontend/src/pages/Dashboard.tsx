import { Link } from "react-router-dom";
import { Flame, Leaf, Scale, Truck, ScanSearch, CalendarDays, Trophy } from "lucide-react";
import { useAuth } from "../auth";
import { api } from "../api";
import { Empty, Load, Notice, Page, Pill, Stat, StatusPill, useLoad, when, fmt, DataBadge } from "../components/ui";

export default function Dashboard() {
  const { user } = useAuth();
  const s = useLoad("/home");
  return (
    <Page title={`Namaste, ${user.name.split(" ")[0]}`} subtitle="Your waste, your points, your impact — all verified step by step.">
      <Load state={s}>{(d: any) => (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Stat label="Spendable GreenPoints" value={fmt(d.balances.spendable, 0)} sub={`+${d.balances.provisional} provisional (not yet spendable)`} />
            <Stat label="Clean-segregation streak" value={<span className="flex items-center gap-1"><Flame size={20} className="text-amber" />{d.streak_days} d</span>} sub={`Score ${fmt(d.segregation_score, 0)}/100`} tone="amber" />
            <Stat label="Verified handed over" value={`${fmt(d.verified_kg)} kg`} sub={`${d.collections} confirmed pickups`} tone="blue" />
            <Stat label="CO₂e avoided (est.)" value={`${fmt(d.impact?.estimated_co2e_avoided_kg)} kg`} sub="Estimate — factor-based" badge="estimate" />
          </div>
          <div className="grid lg:grid-cols-3 gap-4">
            <div className="card lg:col-span-2">
              <div className="flex items-center justify-between mb-2"><h2 className="font-bold">Quick actions</h2></div>
              <div className="grid sm:grid-cols-3 gap-2">
                <Link to="/doctor" className="btn-primary"><ScanSearch size={16} />Scan an item</Link>
                <Link to="/pickups" className="btn-secondary"><Truck size={16} />Schedule pickup</Link>
                <Link to="/hotspots" className="btn-secondary">Report garbage</Link>
              </div>
              <h3 className="font-semibold mt-5 mb-2 text-sm">Upcoming pickup</h3>
              {d.upcoming_pickup ? (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-mint/50 p-3 text-sm">
                  <div><b>{d.upcoming_pickup.detected_object || d.upcoming_pickup.stream}</b> · ~{d.upcoming_pickup.est_weight_kg} kg · {when(d.upcoming_pickup.scheduled_for)}<div className="text-xs text-ink/60">Collector: {d.upcoming_pickup.worker_code || "to be assigned"} · show your household QR/ID: <b>{user.household_code}</b></div></div>
                  <StatusPill s={d.upcoming_pickup.status} />
                </div>
              ) : <Empty title="No pickup scheduled" hint="Scan a dry or wet item to schedule one." />}
              <h3 className="font-semibold mt-5 mb-2 text-sm">Recent activity</h3>
              {d.recent.length === 0 ? <Empty title="No submissions yet" hint="Use the AI Waste Doctor, then submit a segregated item." /> : (
                <table className="w-full"><tbody>{d.recent.map((r: any) => <tr key={r.id}><td className="td">{r.object || "Item"}</td><td className="td text-ink/60">{r.stream}</td><td className="td"><StatusPill s={r.status} /></td><td className="td text-xs text-ink/50">{when(r.at)}</td></tr>)}</tbody></table>
              )}
            </div>
            <div className="space-y-4">
              <div className="card">
                <h2 className="font-bold mb-2 flex items-center gap-2"><Leaf size={16} className="text-fresh" />Nudges for you</h2>
                {d.nudges?.length ? <ul className="space-y-2 text-sm">{d.nudges.map((n: any, i: number) => <li key={i} className="rounded-lg bg-cream p-2"><b>{n.title}</b> {n.body}</li>)}</ul> : <Empty title="You’re all caught up" />}
              </div>
              <div className="card">
                <h2 className="font-bold mb-2 flex items-center gap-2"><Trophy size={16} className="text-amber" />My community</h2>
                {d.my_community ? <div className="text-sm"><b>{d.my_community.name}</b><div>Rank #{d.my_community.rank} · quality score {fmt(d.my_community.score, 0)}</div></div> : <div className="text-sm text-ink/60">You haven’t joined a community yet. <Link to="/community" className="underline text-deep">Join one</Link>.</div>}
              </div>
            </div>
          </div>
          <div className="grid lg:grid-cols-3 gap-4">
            <div className="card lg:col-span-2">
              <h2 className="font-bold mb-2">My Waste Passports</h2>
              {d.passports.length === 0 ? <Empty title="No passports yet" hint="A passport is created when a collector confirms your handover." /> : d.passports.map((p: any) => (
                <Link key={p.id} to={`/passports?ref=${p.code}`} className="flex items-center justify-between rounded-lg border p-3 mb-2 hover:border-forest text-sm"><div><b>{p.code}</b> · {p.input_kg} kg · {p.material_key || p.stream}<div className="text-xs text-ink/60">{p.status_text}</div></div><StatusPill s={p.status} /></Link>
              ))}
            </div>
            <div className="card">
              <h2 className="font-bold mb-2 flex items-center gap-2"><CalendarDays size={16} />Challenges & events</h2>
              {[...d.challenges.map((c: any) => ({ k: "c" + c.id, t: c.title, s: `${c.joined ? c.progress + "/" + c.target : "Open"} · ${c.points_reward} pts` })), ...d.events.map((e: any) => ({ k: "e" + e.id, t: e.name, s: when(e.starts_at) }))].slice(0, 6).map((x: any) => <div key={x.k} className="text-sm py-1.5 border-b last:border-0"><div className="font-medium">{x.t}</div><div className="text-xs text-ink/60">{x.s}</div></div>)}
              <div className="mt-3 flex gap-2"><Link className="btn-secondary btn-sm" to="/community">Challenges</Link><Link className="btn-secondary btn-sm" to="/events">Events</Link></div>
            </div>
          </div>
          <Notice>Points: <b>provisional</b> after your submission is verified → <b>verified</b> after the collector confirms weight → <b>final recovery bonus</b> only when a facility confirms recovered quantity.</Notice>
        </>
      )}</Load>
    </Page>
  );
}
