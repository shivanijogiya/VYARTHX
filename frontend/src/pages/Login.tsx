import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import Logo from "../components/Logo";
import { ErrorBox, Notice, Pill } from "../components/ui";

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
  return (
    <div className="min-h-full grid lg:grid-cols-2">
      <div className="bg-forest text-white p-8 lg:p-14 flex flex-col justify-center">
        <Logo light size={44} />
        <h1 className="text-3xl lg:text-4xl font-extrabold mt-8 leading-tight">India’s AI-Powered City Waste Intelligence &amp; Circular Economy Platform</h1>
        <p className="mt-4 text-mint text-lg">{meta?.tagline || "Segregate better. Earn responsibly. Recover more. Waste less."}</p>
        <ul className="mt-8 space-y-2 text-sm text-mint/90 list-disc pl-5">
          <li>AI Waste Doctor, verified GreenPoints and a tamper-evident Waste Passport</li>
          <li>Agentic workflows with human approval gates and a full audit trail</li>
          <li>Dynamic collection, Digital Twin and landfill intelligence for city teams</li>
        </ul>
        <div className="mt-8 text-xs text-mint/70">Bharat Agentic-AI Hackathon 2026 · Track 3 · Waste Management{meta?.pilot ? ` · ${meta.pilot}` : ""}</div>
      </div>
      <div className="p-6 lg:p-14 flex flex-col justify-center max-w-xl w-full mx-auto">
        <h2 className="text-2xl font-bold text-forest">{mode === "in" ? "Sign in" : "Create your account"}</h2>
        <form onSubmit={submit} className="mt-4 space-y-3">
          {mode === "up" && <div><label className="label" htmlFor="n">Full name</label><input id="n" className="input" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} /></div>}
          <div><label className="label" htmlFor="e">Email</label><input id="e" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" /></div>
          <div><label className="label" htmlFor="p">Password</label><input id="p" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === "up" ? 8 : 1} autoComplete={mode === "in" ? "current-password" : "new-password"} /></div>
          {mode === "up" && (
            <div className="grid grid-cols-2 gap-3">
              <div><label className="label" htmlFor="r">I am a</label><select id="r" className="input" value={role} onChange={(e) => setRole(e.target.value)}><option value="citizen">Citizen</option><option value="worker">Waste worker</option><option value="organiser">Event organiser</option></select></div>
              <div><label className="label" htmlFor="w">Ward / locality</label><select id="w" className="input" value={ward} onChange={(e) => setWard(e.target.value ? Number(e.target.value) : "")}><option value="">Select…</option>{meta?.wards?.map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></div>
            </div>
          )}
          {err && <ErrorBox error={err} />}
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Please wait…" : mode === "in" ? "Sign in" : "Create account"}</button>
        </form>
        <button className="text-sm text-deep mt-3 underline self-start" onClick={() => { setMode(mode === "in" ? "up" : "in"); setErr(""); }}>{mode === "in" ? "New here? Create an account" : "Have an account? Sign in"}</button>
        {accts.length > 0 && (
          <div className="mt-8">
            <div className="flex items-center gap-2 mb-2"><Pill t="purple">Demo Mode</Pill><span className="text-xs text-ink/60">One-click demo accounts (password <code>{accts[0].password}</code>)</span></div>
            <div className="grid sm:grid-cols-2 gap-2">
              {accts.map((a) => <button key={a.email} onClick={() => quick(a)} disabled={busy} className="text-left card !p-3 hover:border-forest transition"><div className="text-sm font-semibold">{a.name}</div><div className="text-[11px] text-ink/60">{a.description}</div><div className="text-[10px] text-ink/40 mt-0.5">{a.email}</div></button>)}
            </div>
          </div>
        )}
        <div className="mt-6"><Notice>All demo figures are simulated and labelled. No real payments, vehicle dispatch or railway benefits exist in this build.</Notice></div>
      </div>
    </div>
  );
}
