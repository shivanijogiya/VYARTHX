import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import Logo from "../components/Logo";
import { ErrorBox, Pill } from "../components/ui";

export default function Login() {
  const { login, meta, setSession } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [mode, setMode] = useState<"in" | "up">("in");
  const [role, setRole] = useState("citizen");
  const [ward, setWard] = useState<number | "">("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [accts, setAccts] = useState<any[]>([]);
  useEffect(() => { api.get("/auth/demo-accounts").then(setAccts).catch(() => {}); }, []);
  const submit = async (e: any) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      if (mode === "in") await login(email, password);
      else { const r = await api.post("/auth/register", { email, password, name, role, ward_id: ward || null }); setSession(r.token, r.user); }
      nav("/", { replace: true });
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const quick = async (a: any) => { setBusy(true); setErr(""); try { await login(a.email, a.password); nav("/", { replace: true }); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  const big = "input !h-[52px] !text-[17px] !px-4";
  return (
    <div className="min-h-full bg-cream">
      <div className="max-w-[1000px] mx-auto px-4 pt-10 lg:pt-24 pb-10 grid lg:grid-cols-[1fr_400px] gap-10 lg:gap-16 items-start">
        <div className="text-center lg:text-left lg:pt-10">
          <Logo size={56} />
          <h1 className="text-[26px] lg:text-[32px] leading-tight font-normal text-ink mt-5 max-w-[520px] mx-auto lg:mx-0">
            {meta?.tagline || "Segregate better. Earn responsibly. Recover more. Waste less."}
          </h1>
          <p className="mt-3 text-[17px] text-ink/60 max-w-[500px] mx-auto lg:mx-0">India's AI-powered city waste intelligence and circular-economy platform, for citizens, waste workers, recyclers and city teams.</p>
          <div className="hidden lg:grid grid-cols-3 gap-3 mt-8 max-w-[520px]">
            {[["AI Waste Doctor", "Identify any item from a photo"], ["GreenPoints", "Verified rewards for clean waste"], ["Waste Passport", "Track every batch end to end"]].map(([t, d]) => (
              <div key={t} className="card !p-3"><div className="text-[15px] font-semibold">{t}</div><div className="text-[13px] text-ink/60 mt-0.5">{d}</div></div>
            ))}
          </div>
        </div>
        <div>
          <div className="bg-white rounded-lg shadow-pop p-4">
            {mode === "up" && <h2 className="text-[22px] font-bold text-center mb-3">Create a new account</h2>}
            <form onSubmit={submit} className="space-y-3">
              {mode === "up" && <input aria-label="Full name" placeholder="Full name" className={big} value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />}
              <input aria-label="Email" placeholder="Email address" type="email" className={big} value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
              <input aria-label="Password" placeholder="Password" type="password" className={big} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === "up" ? 8 : 1} autoComplete={mode === "in" ? "current-password" : "new-password"} />
              {mode === "up" && (
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="label" htmlFor="r">I am a</label><select id="r" className="input !h-11" value={role} onChange={(e) => setRole(e.target.value)}><option value="citizen">Citizen</option><option value="worker">Waste worker</option><option value="organiser">Event organiser</option></select></div>
                  <div><label className="label" htmlFor="w">Ward / locality</label><select id="w" className="input !h-11" value={ward} onChange={(e) => setWard(e.target.value ? Number(e.target.value) : "")}><option value="">Select…</option>{meta?.wards?.map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></div>
                </div>
              )}
              {err && <ErrorBox error={err} />}
              <button className="btn-primary w-full !h-12 !text-[20px] !font-bold !rounded-md" disabled={busy}>{busy ? "Please wait…" : mode === "in" ? "Log in" : "Sign up"}</button>
            </form>
            <div className="border-t border-line/70 my-5" />
            <div className="text-center">
              <button className="btn !h-12 !px-4 !text-[17px] !font-bold bg-fresh text-white hover:bg-[#2A8D42]" onClick={() => { setMode(mode === "in" ? "up" : "in"); setErr(""); }}>{mode === "in" ? "Create new account" : "Back to log in"}</button>
            </div>
          </div>
          {accts.length > 0 && (
            <div className="mt-5 bg-white rounded-lg shadow-card p-3">
              <div className="flex items-center justify-between px-1 mb-2"><span className="text-[15px] font-semibold">Try a demo account</span><Pill t="purple">password {accts[0].password}</Pill></div>
              <div className="max-h-[260px] overflow-auto -mx-1">
                {accts.map((a) => (
                  <button key={a.email} onClick={() => quick(a)} disabled={busy} className="w-full flex items-center gap-3 rounded-md px-2 py-2 text-left hover:bg-hover disabled:opacity-50">
                    <span className="grid place-items-center h-10 w-10 rounded-full bg-forest text-white text-[15px] font-semibold shrink-0">{a.name.split(/\s+/).slice(0, 2).map((w: string) => w[0]).join("").toUpperCase()}</span>
                    <span className="min-w-0"><span className="block text-[15px] font-semibold truncate">{a.name}</span><span className="block text-[13px] text-ink/60 truncate">{a.description}</span></span>
                  </button>
                ))}
              </div>
            </div>
          )}
          <p className="mt-4 text-[13px] text-ink/60 text-center px-4">All demo figures are simulated and labelled. No real payments, vehicle dispatch or railway benefits exist in this build.</p>
        </div>
      </div>
    </div>
  );
}
