import { useEffect, useRef, useState } from "react";
import { Bot, Minus, SendHorizontal, MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api";

const SUGGESTIONS = ["Where do I put a used battery?", "How many points do I have?", "Upcoming events", "Why segregate waste?"];

export default function Assistant() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<any[]>([{ from: "bot", text: "Hi! I'm the VYARTHX Assistant. Ask me how to dispose of something, check your points, find events or report overflowing garbage." }]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy, open]);
  const send = async (raw?: string) => {
    const text = (raw ?? q).trim(); if (!text || busy) return;
    setMsgs((m) => [...m, { from: "me", text }]); setQ(""); setBusy(true);
    try { const r = await api.post("/assistant", { message: text }); setMsgs((m) => [...m, { from: "bot", text: r.answer, actions: r.actions, run: r.run_id, llm: r.llm_phrased }]); }
    catch (e: any) { setMsgs((m) => [...m, { from: "bot", text: "Sorry, I couldn't process that: " + e.message }]); }
    finally { setBusy(false); }
  };
  return (
    <>
      <button aria-label="Open assistant" onClick={() => setOpen(true)}
        className={`fixed bottom-20 lg:bottom-5 right-4 lg:right-5 z-40 grid place-items-center h-14 w-14 rounded-full bg-white text-forest shadow-pop hover:bg-hover transition ${open ? "hidden" : ""}`}>
        <MessageCircle size={26} fill="currentColor" className="text-forest" />
      </button>
      {open && (
        <div className="fixed bottom-0 right-0 sm:right-5 z-50 w-full sm:w-[360px] h-[75vh] sm:h-[480px] bg-white rounded-t-lg shadow-pop flex flex-col">
          <div className="flex items-center gap-2 px-2 h-12 shadow-nav rounded-t-lg">
            <span className="relative grid place-items-center h-8 w-8 rounded-full bg-forest text-white"><Bot size={17} /><span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full bg-fresh border-2 border-white" /></span>
            <div className="leading-tight"><div className="text-[15px] font-semibold">VYARTHX Assistant</div><div className="text-[12px] text-ink/60">{busy ? "Typing…" : "Active now"}</div></div>
            <button className="ml-auto grid place-items-center h-8 w-8 rounded-full text-forest hover:bg-hover" onClick={() => setOpen(false)} aria-label="Minimise assistant"><Minus size={20} /></button>
          </div>
          <div className="flex-1 overflow-auto px-3 py-3 space-y-1.5 text-[15px]">
            {msgs.map((m, i) => (
              <div key={i} className={m.from === "me" ? "flex flex-col items-end" : "flex flex-col items-start"}>
                <div className={`max-w-[80%] rounded-[18px] px-3 py-2 whitespace-pre-line leading-snug ${m.from === "me" ? "bg-forest text-white" : "bg-btn text-ink"}`}>{m.text}</div>
                {m.actions?.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{m.actions.map((a: any, j: number) => <Link key={j} to={a.to || "/"} onClick={() => setOpen(false)} className="rounded-full border border-forest/30 text-forest px-3 py-1 text-[13px] font-semibold hover:bg-mint">{a.label}</Link>)}</div>}
                {m.run && <Link to={`/agents?run=${m.run}`} onClick={() => setOpen(false)} className="text-[11px] text-ink/50 mt-0.5 ml-2 hover:underline">Agent trace #{m.run}{m.llm ? " · AI-phrased" : ""}</Link>}
              </div>
            ))}
            {msgs.length === 1 && !busy && (
              <div className="flex flex-wrap gap-1.5 pt-2">{SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)} className="rounded-full border border-line px-3 py-1.5 text-[13px] hover:bg-hover">{s}</button>)}</div>
            )}
            {busy && <div className="inline-flex gap-1 rounded-[18px] bg-btn px-3 py-3">{[0, 1, 2].map((d) => <span key={d} className="h-2 w-2 rounded-full bg-ink/40 animate-bounce" style={{ animationDelay: `${d * 0.15}s` }} />)}</div>}
            <div ref={end} />
          </div>
          <div className="p-2 flex items-center gap-1">
            <input className="flex-1 h-9 rounded-full bg-cream px-4 text-[15px] placeholder:text-ink/50 focus:outline-none" value={q} placeholder="Aa" onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} aria-label="Message" />
            <button className="grid place-items-center h-9 w-9 rounded-full text-forest hover:bg-hover disabled:opacity-40" onClick={() => send()} disabled={busy || !q.trim()} aria-label="Send"><SendHorizontal size={20} /></button>
          </div>
        </div>
      )}
    </>
  );
}
