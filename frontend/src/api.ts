const TOKEN_KEY = "vyarthx_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

async function handle(r: Response) {
  if (r.status === 401) { setToken(null); if (!location.pathname.startsWith("/login")) location.href = "/login"; }
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: any) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join("; ") : msg;
    } catch { /* ignore */ }
    throw new ApiError(r.status, msg);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("json") ? r.json() : r.text();
}
const headers = (extra: any = {}) => ({ ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}), ...extra });

export const api = {
  get: (p: string) => fetch("/api" + p, { headers: headers() }).then(handle),
  post: (p: string, body?: any) => fetch("/api" + p, { method: "POST", headers: headers({ "Content-Type": "application/json" }), body: JSON.stringify(body ?? {}) }).then(handle),
  put: (p: string, body?: any) => fetch("/api" + p, { method: "PUT", headers: headers({ "Content-Type": "application/json" }), body: JSON.stringify(body ?? {}) }).then(handle),
  patch: (p: string, body?: any) => fetch("/api" + p, { method: "PATCH", headers: headers({ "Content-Type": "application/json" }), body: JSON.stringify(body ?? {}) }).then(handle),
  form: (p: string, fd: FormData) => fetch("/api" + p, { method: "POST", headers: headers(), body: fd }).then(handle),
};

export function fd(obj: Record<string, any>) {
  const f = new FormData();
  Object.entries(obj).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") f.append(k, v as any); });
  return f;
}
