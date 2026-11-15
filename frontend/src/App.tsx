import { useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Menu, X, LogOut, Home, ScanSearch, Wallet, Gift, FileText, Store, Recycle, Sprout, AlertOctagon, Trophy, CalendarDays, MapPin, Truck, Users, Building2, Landmark, FlaskConical, BarChart3, Bot, Database, Factory, Package, PlayCircle, Siren, Search } from "lucide-react";
import { useAuth } from "./auth";
import Logo from "./components/Logo";
import Assistant from "./components/Assistant";
import { Spinner } from "./components/ui";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import WasteDoctor from "./pages/WasteDoctor";
import WalletPage from "./pages/Wallet";
import Rewards from "./pages/Rewards";
import Passports from "./pages/Passports";
import Marketplace from "./pages/Marketplace";
import Reuse from "./pages/Reuse";
import Compost from "./pages/Compost";
import Special from "./pages/Special";
import Community from "./pages/Community";
import Events from "./pages/Events";
import Hotspots from "./pages/Hotspots";
import Pickups from "./pages/Pickups";
import WorkerPortal from "./pages/Worker";
import FacilityPortal from "./pages/Facility";
import Command from "./pages/Command";
import Logistics from "./pages/Logistics";
import Landfill from "./pages/Landfill";
import Twin from "./pages/Twin";
import Reports from "./pages/Reports";
import AgentCentre from "./pages/Agents";
import Sources from "./pages/Sources";
import DemoGuide from "./pages/DemoGuide";

type NavItem = { to: string; label: string; icon: any; roles?: string[] };
const NAV: { group: string; items: NavItem[] }[] = [
  { group: "Community", items: [
    { to: "/", label: "Dashboard", icon: Home, roles: ["citizen", "organiser"] },
    { to: "/doctor", label: "AI Waste Doctor", icon: ScanSearch, roles: ["citizen", "organiser", "worker"] },
    { to: "/pickups", label: "Pickups", icon: Truck, roles: ["citizen", "organiser"] },
    { to: "/wallet", label: "GreenPoints Wallet", icon: Wallet, roles: ["citizen", "organiser"] },
    { to: "/rewards", label: "Redeem Rewards", icon: Gift, roles: ["citizen", "organiser"] },
    { to: "/passports", label: "Waste Passport", icon: FileText, roles: ["citizen", "organiser", "municipal", "facility", "recycler"] },
    { to: "/community", label: "Neighbourhood League", icon: Trophy, roles: ["citizen", "organiser", "municipal"] },
    { to: "/hotspots", label: "Report & Hotspots", icon: MapPin, roles: ["citizen", "organiser", "municipal", "worker"] },
  ] },
  { group: "Circular economy", items: [
    { to: "/marketplace", label: "Circular Marketplace", icon: Store, roles: ["citizen", "organiser", "recycler", "facility", "municipal"] },
    { to: "/reuse", label: "Reuse & Upcycling", icon: Recycle, roles: ["citizen", "organiser", "municipal"] },
    { to: "/compost", label: "Compost-to-Community", icon: Sprout, roles: ["citizen", "organiser", "municipal", "facility"] },
    { to: "/special", label: "E-waste & Special Care", icon: AlertOctagon, roles: ["citizen", "organiser", "municipal", "worker", "facility"] },
    { to: "/events", label: "Zero-Waste Events", icon: CalendarDays, roles: ["citizen", "organiser", "municipal", "facility", "recycler"] },
  ] },
  { group: "Operations", items: [
    { to: "/worker", label: "Worker Portal", icon: Users, roles: ["worker"] },
    { to: "/facility", label: "Facility Desk", icon: Factory, roles: ["facility", "recycler"] },
    { to: "/command", label: "Command Centre", icon: Building2, roles: ["municipal"] },
    { to: "/logistics", label: "Dynamic Collection", icon: Package, roles: ["municipal"] },
    { to: "/landfill", label: "Landfill Intelligence", icon: Landmark, roles: ["municipal"] },
    { to: "/twin", label: "Digital Twin", icon: FlaskConical, roles: ["municipal"] },
    { to: "/reports", label: "Analytics & Reports", icon: BarChart3, roles: ["municipal", "citizen"] },
  ] },
  { group: "Platform", items: [
    { to: "/agents", label: "AI Agent Centre", icon: Bot },
    { to: "/demo", label: "Guided Demo", icon: PlayCircle },
    { to: "/sources", label: "Data & Honesty", icon: Database },
  ] },
];
const HOME: Record<string, string> = { citizen: "/", organiser: "/", worker: "/worker", facility: "/facility", recycler: "/facility", municipal: "/command" };

function initials(name: string) {
  return (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}
export function Avatar({ name, size = 36 }: { name: string; size?: number }) {
  return <span className="grid place-items-center rounded-full bg-forest text-white font-semibold shrink-0" style={{ width: size, height: size, fontSize: size * 0.4 }}>{initials(name)}</span>;
}

function Shell({ children }: { children: any }) {
  const { user, meta, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const loc = useLocation();
  const navigate = useNavigate();
  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => !i.roles || i.roles.includes(user.role)) })).filter((g) => g.items.length);
  const all = groups.flatMap((g) => g.items);
  const hits = q.trim() ? all.filter((i) => i.label.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 6) : [];
  const go = (to: string) => { setQ(""); setOpen(false); navigate(to); };
  const sidebar = (
    <nav className="px-2 py-3 overflow-y-auto h-full pb-24" aria-label="Main">
      <div className="flex items-center gap-3 rounded-lg px-2 py-2 mb-1">
        <Avatar name={user.name} />
        <div className="min-w-0 leading-tight"><div className="text-[15px] font-semibold truncate">{user.name}</div><div className="text-[13px] text-ink/60 capitalize truncate">{user.role}{user.ward ? ` · ${user.ward}` : ""}</div></div>
      </div>
      {groups.map((g, gi) => (
        <div key={g.group} className={gi ? "mt-2 pt-2 border-t border-line/70" : ""}>
          <div className="px-2 pt-2 pb-1 text-[15px] font-semibold text-ink/60">{g.group}</div>
          {g.items.map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === "/"} onClick={() => setOpen(false)}
              className={({ isActive }) => `group flex items-center gap-3 rounded-lg px-2 h-12 text-[15px] font-medium transition-colors ${isActive ? "bg-mint text-forest" : "text-ink hover:bg-black/5"}`}>
              {({ isActive }) => (<>
                <span className={`grid place-items-center h-9 w-9 rounded-full shrink-0 ${isActive ? "bg-forest text-white" : "bg-btn text-ink/70 group-hover:bg-[#D8DADF]"}`}><i.icon size={18} /></span>
                <span className="truncate">{i.label}</span>
              </>)}
            </NavLink>
          ))}
        </div>
      ))}
      <div className="px-2 mt-4 text-[12px] text-ink/50 leading-relaxed">{meta?.tagline}</div>
    </nav>
  );
  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-30 bg-white shadow-nav">
        <div className="flex items-center gap-2 px-3 sm:px-4 h-14">
          <button className="icon-btn lg:hidden" onClick={() => setOpen(!open)} aria-label="Toggle menu">{open ? <X size={20} /> : <Menu size={20} />}</button>
          <NavLink to={HOME[user.role] || "/"} aria-label="Home"><Logo size={40} text={false} /></NavLink>
          <div className="relative hidden sm:block w-60 xl:w-72">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/50" />
            <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && hits[0]) go(hits[0].to); if (e.key === "Escape") setQ(""); }}
              placeholder="Search VYARTHX" aria-label="Search pages" className="w-full h-10 rounded-full bg-cream pl-9 pr-3 text-[15px] placeholder:text-ink/50 focus:outline-none focus:ring-2 focus:ring-forest/30" />
            {hits.length > 0 && (
              <div className="absolute left-0 right-0 top-12 bg-white rounded-lg shadow-pop p-2 z-40">
                {hits.map((h) => <button key={h.to} onClick={() => go(h.to)} className="w-full flex items-center gap-3 rounded-md px-2 py-2 text-left hover:bg-hover"><span className="grid place-items-center h-8 w-8 rounded-full bg-btn"><h.icon size={16} /></span><span className="text-[15px]">{h.label}</span></button>)}
              </div>
            )}
          </div>
          <div className="ml-auto flex items-center gap-2">
            {meta?.demo_mode && <span className="hidden md:inline-flex items-center gap-1.5 rounded-full bg-cream px-3 h-8 text-[13px] font-semibold text-ink/70"><span className="h-2 w-2 rounded-full bg-amber" />Demo · simulated data</span>}
            <div className="hidden sm:flex items-center gap-2 rounded-full hover:bg-black/5 pl-1 pr-3 h-10"><Avatar name={user.name} size={32} /><span className="text-[15px] font-semibold max-w-[10rem] truncate">{user.name.split(" ")[0]}</span></div>
            <button className="icon-btn" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={18} /></button>
          </div>
        </div>
      </header>
      <div className="flex flex-1 min-h-0">
        <aside className="hidden lg:block w-[280px] xl:w-[300px] shrink-0 sticky top-14 h-[calc(100vh-3.5rem)]">{sidebar}</aside>
        {open && <div className="lg:hidden fixed inset-0 top-14 z-20 bg-cream overflow-auto">{sidebar}</div>}
        <main className="flex-1 min-w-0 px-4 py-5 sm:px-6 lg:px-8 max-w-[1100px] mx-auto w-full" key={loc.pathname}>
          {meta?.demo_mode && <div className="mb-4 flex items-start gap-2 rounded-lg bg-white shadow-card px-3 py-2 text-[13px] text-ink/70"><Siren size={15} className="mt-0.5 shrink-0 text-amber" /><span>Demo environment: people, facilities, weights and histories are <b className="text-ink">simulated</b>. No real payments, vehicle dispatch or municipal integrations are connected.</span></div>}
          {children}
        </main>
      </div>
      <Assistant />
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="h-full grid place-items-center"><Spinner label="Starting VYARTHX…" /></div>;
  if (!user) return <Routes><Route path="/login" element={<Login />} /><Route path="*" element={<Navigate to="/login" replace />} /></Routes>;
  const r = (el: any, roles: string[]) => (roles.includes(user.role) ? el : <Navigate to={HOME[user.role] || "/"} replace />);
  const cit = ["citizen", "organiser"];
  return (
    <Shell>
      <Routes>
        <Route path="/login" element={<Navigate to={HOME[user.role] || "/"} replace />} />
        <Route path="/" element={cit.includes(user.role) ? <Dashboard /> : <Navigate to={HOME[user.role]} replace />} />
        <Route path="/doctor" element={<WasteDoctor />} />
        <Route path="/pickups" element={r(<Pickups />, cit)} />
        <Route path="/wallet" element={r(<WalletPage />, cit)} />
        <Route path="/rewards" element={r(<Rewards />, cit)} />
        <Route path="/passports" element={<Passports />} />
        <Route path="/community" element={<Community />} />
        <Route path="/hotspots" element={<Hotspots />} />
        <Route path="/marketplace" element={<Marketplace />} />
        <Route path="/reuse" element={<Reuse />} />
        <Route path="/compost" element={<Compost />} />
        <Route path="/special" element={<Special />} />
        <Route path="/events" element={<Events />} />
        <Route path="/worker" element={r(<WorkerPortal />, ["worker"])} />
        <Route path="/facility" element={r(<FacilityPortal />, ["facility", "recycler"])} />
        <Route path="/command" element={r(<Command />, ["municipal"])} />
        <Route path="/logistics" element={r(<Logistics />, ["municipal"])} />
        <Route path="/landfill" element={r(<Landfill />, ["municipal"])} />
        <Route path="/twin" element={r(<Twin />, ["municipal"])} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/agents" element={<AgentCentre />} />
        <Route path="/demo" element={<DemoGuide />} />
        <Route path="/sources" element={<Sources />} />
        <Route path="*" element={<Navigate to={HOME[user.role] || "/"} replace />} />
      </Routes>
    </Shell>
  );
}
