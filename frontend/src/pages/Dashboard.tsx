import { useState } from "react";
import { Link } from "react-router-dom";
import { Flame, Truck, ScanSearch, CalendarDays, Trophy, MapPin, Gift, ChevronRight, Lightbulb, X, Leaf, Scale, Package, Store } from "lucide-react";
import { useAuth } from "../auth";
import { Empty, Load, StatusPill, useLoad, when, fmt } from "../components/ui";

const SHORTCUTS = [
  { to: "/pickups", label: "Pickups", icon: Truck, bg: "bg-[#45BD62]" },
  { to: "/marketplace", label: "Sell / swap", icon: Store, bg: "bg-forest" },
  { to: "/hotspots", label: "Report", icon: MapPin, bg: "bg-coral" },
  { to: "/rewards", label: "Rewards", icon: Gift, bg: "bg-[#F7B928]" },
];

function Section({ title, to, children }: { title: string; to?: string; children: any }) {
  return (
    <section className="card">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-[17px] font-bold">{title}</h2>
        {to && <Link to={to} className="text-[15px] text-forest hover:bg-hover rounded-md px-2 py-1 -mr-2">See all</Link>}
      </div>
      {children}
    </section>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const s = useLoad("/home");
  const [tipHidden, setTipHidden] = useState(false);
  const first = user.name.split(" ")[0];
  return (
    <Load state={s}>{(d: any) => {
      const tip = d.nudges?.[0];
      const upcoming = [
        ...d.events.map((e: any) => ({ k: "e" + e.id, t: e.name, s: when(e.starts_at), icon: CalendarDays, to: "/events" })),
        ...d.challenges.map((c: any) => ({ k: "c" + c.id, t: c.title, s: c.joined ? `${c.progress}/${c.target} done · ${c.points_reward} pts` : `${c.points_reward} pts reward`, icon: Trophy, to: "/community" })),
      ].slice(0, 3);
      return (
        <div className="grid lg:grid-cols-[1fr_300px] gap-4 items-start">
          {/* ---------- main feed ---------- */}
          <div className="space-y-4 min-w-0">
            {/* Hero */}
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-[#0866FF] via-[#1877F2] to-[#5B8DEF] text-white p-5 sm:p-6 shadow-card">
              <div className="absolute -right-10 -top-10 h-44 w-44 rounded-full bg-white/10" />
              <div className="absolute right-16 -bottom-16 h-40 w-40 rounded-full bg-white/10" />
              <div className="relative">
                <div className="text-[15px] text-white/80">Namaste, {first}</div>
                <div className="mt-1 flex items-end gap-2">
                  <span className="text-[44px] leading-none font-bold tracking-tight">{fmt(d.balances.spendable, 0)}</span>
                  <span className="pb-1 text-[17px] font-semibold">GreenPoints</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-[13px]">
                  {d.balances.provisional > 0 && <span className="rounded-full bg-white/20 px-2.5 py-1">+{d.balances.provisional} pending verification</span>}
                  <span className="rounded-full bg-white/20 px-2.5 py-1 inline-flex items-center gap-1"><Flame size={13} />{d.streak_days}-day streak</span>
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Link to="/doctor" className="btn !h-10 bg-white text-forest hover:bg-white/90"><ScanSearch size={18} />Scan an item</Link>
                  <Link to="/wallet" className="btn !h-10 bg-white/15 text-white hover:bg-white/25">View wallet</Link>
                </div>
              </div>
            </div>

            {/* Shortcuts */}
            <div className="grid grid-cols-4 gap-2">
              {SHORTCUTS.map((x) => (
                <Link key={x.to} to={x.to} className="card !p-3 flex flex-col items-center gap-2 hover:bg-hover transition-colors">
                  <span className={`grid place-items-center h-11 w-11 rounded-full text-white ${x.bg}`}><x.icon size={20} /></span>
                  <span className="text-[13px] font-semibold text-center">{x.label}</span>
                </Link>
              ))}
            </div>

            {/* Tip of the day */}
            {tip && !tipHidden && (
              <div className="card flex gap-3 items-start">
                <span className="grid place-items-center h-10 w-10 rounded-full bg-[#FEF5E0] text-[#B07800] shrink-0"><Lightbulb size={20} /></span>
                <div className="min-w-0 flex-1"><div className="text-[15px] font-semibold">{tip.title}</div><div className="text-[14px] text-ink/70 mt-0.5">{tip.body}</div></div>
                <button onClick={() => setTipHidden(true)} className="grid place-items-center h-8 w-8 rounded-full hover:bg-hover text-ink/60" aria-label="Dismiss tip"><X size={18} /></button>
              </div>
            )}

            {/* Next pickup */}
            <Section title="Next pickup" to="/pickups">
              {d.upcoming_pickup ? (
                <div className="flex items-center gap-3">
                  <span className="grid place-items-center h-12 w-12 rounded-full bg-mint text-forest shrink-0"><Truck size={22} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[15px] font-semibold truncate">{d.upcoming_pickup.detected_object || d.upcoming_pickup.stream} · ~{d.upcoming_pickup.est_weight_kg} kg</div>
                    <div className="text-[13px] text-ink/60">{when(d.upcoming_pickup.scheduled_for)} · show ID <b className="text-ink">{user.household_code}</b></div>
                  </div>
                  <StatusPill s={d.upcoming_pickup.status} />
                </div>
              ) : <Empty title="No pickup scheduled" hint="Scan an item to schedule one."><Link to="/doctor" className="btn-primary btn-sm">Scan an item</Link></Empty>}
            </Section>

            {/* Recent activity */}
            <Section title="Recent activity" to="/passports">
              {d.recent.length === 0 ? <Empty title="No submissions yet" hint="Use the AI Waste Doctor to submit your first item." /> : (
                <div className="-mx-2">
                  {d.recent.slice(0, 4).map((r: any) => (
                    <div key={r.id} className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-hover">
                      <span className="grid place-items-center h-9 w-9 rounded-full bg-btn text-ink/70 shrink-0"><Package size={17} /></span>
                      <div className="min-w-0 flex-1"><div className="text-[15px] font-medium truncate">{r.object || "Item"}</div><div className="text-[13px] text-ink/60"><span className="capitalize">{r.stream}</span> · {when(r.at)}</div></div>
                      <StatusPill s={r.status} />
                    </div>
                  ))}
                </div>
              )}
            </Section>
          </div>

          {/* ---------- right rail ---------- */}
          <aside className="space-y-4">
            <section className="card">
              <h2 className="text-[17px] font-bold mb-3">Your impact</h2>
              <div className="space-y-3">
                {[
                  { icon: Scale, label: "Handed over", value: `${fmt(d.verified_kg)} kg`, c: "bg-mint text-forest" },
                  { icon: Leaf, label: "CO₂e avoided (est.)", value: `${fmt(d.impact?.estimated_co2e_avoided_kg)} kg`, c: "bg-[#E6F4EA] text-fresh" },
                  { icon: Truck, label: "Pickups completed", value: d.collections, c: "bg-[#FEF5E0] text-[#B07800]" },
                ].map((x) => (
                  <div key={x.label} className="flex items-center gap-3">
                    <span className={`grid place-items-center h-9 w-9 rounded-full ${x.c}`}><x.icon size={17} /></span>
                    <span className="flex-1 text-[14px] text-ink/70">{x.label}</span>
                    <span className="text-[15px] font-bold">{x.value}</span>
                  </div>
                ))}
              </div>
            </section>

            <Link to="/community" className="card flex items-center gap-3 hover:bg-hover transition-colors">
              <span className="grid place-items-center h-11 w-11 rounded-full bg-[#FEF5E0] text-[#B07800] shrink-0"><Trophy size={20} /></span>
              {d.my_community
                ? <div className="min-w-0 flex-1"><div className="text-[15px] font-semibold truncate">{d.my_community.name}</div><div className="text-[13px] text-ink/60">Rank #{d.my_community.rank} · score {fmt(d.my_community.score, 0)}</div></div>
                : <div className="flex-1"><div className="text-[15px] font-semibold">Join your neighbourhood</div><div className="text-[13px] text-ink/60">Compete in the Green League</div></div>}
              <ChevronRight size={18} className="text-ink/40" />
            </Link>

            {upcoming.length > 0 && (
              <section className="card">
                <h2 className="text-[17px] font-bold mb-1">Coming up</h2>
                <div className="-mx-2">
                  {upcoming.map((x) => (
                    <Link key={x.k} to={x.to} className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-hover">
                      <span className="grid place-items-center h-9 w-9 rounded-full bg-btn text-ink/70 shrink-0"><x.icon size={17} /></span>
                      <div className="min-w-0"><div className="text-[14px] font-semibold truncate">{x.t}</div><div className="text-[12px] text-ink/60">{x.s}</div></div>
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </aside>
        </div>
      );
    }}</Load>
  );
}
