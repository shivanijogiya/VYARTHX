export default function Logo({ size = 32, text = true, light = false }: { size?: number; text?: boolean; light?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="14" fill={light ? "#D1FAE5" : "#166534"} /><path d="M14 18 L32 48 L50 18" fill="none" stroke={light ? "#166534" : "#D1FAE5"} strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" /><circle cx="32" cy="48" r="5" fill="#22C55E" /><path d="M44 12c6 0 8 5 8 9-5 0-8-3-8-9z" fill="#22C55E" /></svg>
      {text && <span className={`font-black tracking-tight text-xl ${light ? "text-white" : "text-forest"}`}>VYARTHX</span>}
    </span>
  );
}
