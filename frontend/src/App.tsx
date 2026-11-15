import { useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { Menu, X, LogOut, Home, ScanSearch, Wallet, Gift, FileText, Store, Recycle, Sprout, AlertOctagon, Trophy, CalendarDays, MapPin, Truck, Users, Building2, Landmark, FlaskConical, BarChart3, Bot, Database, Factory, Package, PlayCircle, Siren } from "lucide-react";
import { useAuth } from "./auth";
import Logo from "./components/Logo";
import Assistant from "./components/Assistant";
import { Spinner, Pill, Notice } from "./components/ui";
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

function Shell({ children }: { children: any }) {
  const { user, meta, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => !i.roles || i.roles.includes(user.role)) })).filter((g) => g.items.length);
  const sidebar = (
    <nav className="p-3 space-y-4 overflow-y-auto h-full pb-24" aria-label="Main">
      {groups.map((g) => (
        <div key={g.group}>
          <div className="px-2 text-[10px] font-bold uppercase tracking-wider text-ink/40 mb-1">{g.group}</div>
          {g.items.map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === "/"} onClick={() => setOpen(false)} className={({ isActive }) => `flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium ${isActive ? "bg-forest text-white" : "text-ink/80 hover:bg-mint"}`}>
              <i.icon size={17} />{i.label}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-30 bg-white border-b border-green-900/10">
        <div className="flex items-center gap-3 px-4 h-14">
          <button className="lg:hidden p-1" onClick={() => setOpen(!open)} aria-label="Toggle menu">{open ? <X /> : <Menu />}</button>
          <Logo />
          <span className="hidden md:block text-xs text-ink/50">{meta?.tagline}</span>
          <div className="ml-auto flex items-center gap-3">
            {meta?.demo_mode && <Pill t="purple">Demo Mode · simulated data</Pill>}
            <div className="hidden sm:block text-right leading-tight"><div className="text-sm font-semibold">{user.name}</div><div className="text-[11px] text-ink/50">{user.role}{user.ward ? ` · ${user.ward}` : ""}</div></div>
            <button className="btn-secondary btn-sm" onClick={logout} aria-label="Sign out"><LogOut size={14} />Sign out</button>
          </div>
        </div>
      </header>
      <div className="flex flex-1 min-h-0">
        <aside className="hidden lg:block w-64 shrink-0 bg-white border-r border-green-900/10 sticky top-14 h-[calc(100vh-3.5rem)]">{sidebar}</aside>
        {open && <div className="lg:hidden fixed inset-0 top-14 z-20 bg-white overflow-auto">{sidebar}</div>}
        <main className="flex-1 min-w-0 p-4 sm:p-6 max-w-7xl mx-auto w-full" key={loc.pathname}>
          {meta?.demo_mode && <div className="mb-4"><Notice t="amber" icon={<Siren size={16} className="mt-0.5 shrink-0" />}>Demo environment: people, facilities, weights and histories are <b>simulated</b>. No real payments, vehicle dispatch, rail benefits or municipal integrations are connected.</Notice></div>}
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
