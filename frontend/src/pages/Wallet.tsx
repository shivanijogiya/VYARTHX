import { Link } from "react-router-dom";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Load, Notice, Page, Pill, Stat, useLoad, when, fmt, Empty } from "../components/ui";

const kindTone: any = { provisional_credit: "amber", verified_credit: "green", final_credit: "green", bonus: "blue", redemption: "red", reversal: "red", conversion: "gray" };
export default function WalletPage() {
  const w = useLoad("/wallet");
  return (
    <Page title="GreenPoints Wallet" subtitle="A deterministic ledger — agents request entries, but balances come only from backend rules.">
      <Load state={w}>{(d: any) => {
        const b = d.balances;
        let run = 0;
        const series = [...d.transactions].reverse().map((t: any) => { run += t.amount; return { d: when(t.created_at), pts: run }; });
        return (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <Stat label="Spendable" value={fmt(b.spendable, 0)} sub="Verified + final" />
              <Stat label="Provisional" value={fmt(b.provisional, 0)} sub="Awaiting collector verification" tone="amber" />
              <Stat label="Verified" value={fmt(b.verified, 0)} sub="Confirmed handover" tone="blue" />
              <Stat label="Final recovery" value={fmt(b.final, 0)} sub="Facility-confirmed recovery" />
            </div>
            <div className="grid lg:grid-cols-3 gap-4">
              <div className="card lg:col-span-2">
                <div className="flex justify-between items-center mb-1"><h2 className="font-bold">Level: {b.level}</h2><span className="text-xs text-ink/60">{b.next_level ? `${fmt(b.next_level_at - b.lifetime_earned, 0)} pts to ${b.next_level}` : "Top level"}</span></div>
                <div className="h-2 bg-btn rounded-full overflow-hidden"><div className="h-full bg-fresh" style={{ width: `${Math.min(100, (b.lifetime_earned / (b.next_level_at || b.lifetime_earned || 1)) * 100)}%` }} /></div>
                <div className="grid grid-cols-3 gap-3 mt-4 text-sm"><div><div className="text-ink/50 text-xs">7 days</div><b>+{d.earned_7d}</b></div><div><div className="text-ink/50 text-xs">30 days</div><b>+{d.earned_30d}</b></div><div><div className="text-ink/50 text-xs">Streak</div><b>{d.streak_days} days</b></div></div>
                {series.length > 1 && <div className="h-44 mt-3"><ResponsiveContainer><AreaChart data={series}><XAxis dataKey="d" hide /><YAxis width={36} fontSize={11} /><Tooltip /><Area dataKey="pts" stroke="#0866FF" fill="#E7F3FF" /></AreaChart></ResponsiveContainer></div>}
              </div>
              <div className="card text-sm space-y-2">
                <h2 className="font-bold">How points work</h2>
                {Object.entries(d.rules).map(([k, v]: any) => <div key={k}><b className="capitalize">{k}:</b> {v}</div>)}
                <div className="text-xs text-ink/60">Rates (pts/kg): {Object.entries(d.rates_per_kg).map(([k, v]) => `${k} ${v}`).join(" · ")}</div>
                <Link to="/rewards" className="btn-primary w-full">Redeem rewards</Link>
              </div>
            </div>
            <div className="card">
              <h2 className="font-bold mb-2">Transaction history</h2>
              {d.transactions.length === 0 ? <Empty title="No transactions yet" /> : <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">When</th><th className="th">Type</th><th className="th">Bucket</th><th className="th">Points</th><th className="th">Note</th></tr></thead><tbody>
                {d.transactions.map((t: any) => <tr key={t.id}><td className="td whitespace-nowrap">{when(t.created_at)}</td><td className="td"><Pill t={kindTone[t.kind] || "gray"}>{t.kind.replace(/_/g, " ")}</Pill></td><td className="td">{t.bucket}</td><td className={`td font-bold ${t.amount < 0 ? "text-coral" : "text-fresh"}`}>{t.amount > 0 ? "+" : ""}{t.amount}</td><td className="td text-ink/70">{t.note}</td></tr>)}
              </tbody></table></div>}
            </div>
            {d.redemptions.length > 0 && <div className="card"><h2 className="font-bold mb-2">My redemptions</h2>{d.redemptions.map((r: any) => <div key={r.id} className="text-sm py-1 border-b last:border-0 flex justify-between"><span>{r.title} <Pill t="purple">demo voucher</Pill></span><span>{r.points} pts · code {r.voucher_code}</span></div>)}</div>}
            <Notice>Demo ledger — no real money or benefit is issued. Points have no cash value in this build.</Notice>
          </>
        );
      }}</Load>
    </Page>
  );
}
