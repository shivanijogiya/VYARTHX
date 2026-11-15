import { useState } from "react";
import { Bot, Send, X } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function Assistant() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<any[]>([{ from: "bot", text: "Hi! Ask about disposal (e.g. “Where do I put a used battery?”), your points, events, pickups or reporting overflow." }]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    const text = q.trim(); if (!text || busy) return;
    setMsgs((m) => [...m, { from: "me", text }]); setQ(""); setBusy(true);
    try { const r = await api.post("/assistant", { message: text }); setMsgs((m) => [...m, { from: "bot", text: r.answer, actions: r.actions, run: r.run_id, llm: r.llm_phrased }]); }
    catch (e: any) { setMsgs((m) => [...m, { from: "bot", text: "Sorry — I couldn’t process that: " + e.message }]); }
    finally { setBusy(false); }
  };
  return (
    <>
      <button aria-label="Open assistant" onClick={() => setOpen(true)} className={`fixed bottom-5 right-5 z-40 rounded-full bg-forest text-white p-4 shadow-xl hover:bg-green-800 ${open ? "hidden" : ""}`}><Bot /></button>
      {open && (
        <div className="fixed bottom-0 right-0 sm:bottom-5 sm:right-5 z-50 w-full sm:w-96 h-[70vh] sm:h-[32rem] bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col border border-green-900/10">
          <div className="flex items-center justify-between bg-forest text-white px-4 py-3 rounded-t-2xl"><div className="font-bold flex items-center gap-2"><Bot size={18} />VYARTHX Assistant</div><button onClick={() => setOpen(false)} aria-label="Close assistant"><X size={18} /></button></div>
          <div className="flex-1 overflow-auto p-3 space-y-2 text-sm">
            {msgs.map((m, i) => (
              <div key={i} className={m.from === "me" ? "text-right" : ""}>
                <div className={`inline-block max-w-[88%] rounded-xl px-3 py-2 text-left whitespace-pre-line ${m.from === "me" ? "bg-mint" : "bg-gray-100"}`}>{m.text}</div>
                {m.actions?.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{m.actions.map((a: any, j: number) => <Link key={j} to={a.to || "/"} onClick={() => setOpen(false)} className="btn-secondary btn-sm">{a.label}</Link>)}</div>}
                {m.run && <div className="text-[10px] text-ink/50 mt-0.5"><Link to={`/agents?run=${m.run}`} onClick={() => setOpen(false)} className="underline">View agent trace #{m.run}</Link>{m.llm ? " · LLM-phrased" : " · deterministic"}</div>}
              </div>
            ))}
            {busy && <div className="text-xs text-ink/50">Thinking…</div>}
          </div>
          <div className="p-2 border-t flex gap-2"><input className="input" value={q} placeholder="Ask anything about waste…" onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} aria-label="Message" /><button className="btn-primary" onClick={send} disabled={busy} aria-label="Send"><Send size={16} /></button></div>
        </div>
      )}
    </>
  );
}
