export default function Logo({ size = 32, text = true, light = false }: { size?: number; text?: boolean; light?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="32" r="32" fill={light ? "#FFFFFF" : "#0866FF"} />
        <path d="M17 21 L32 45 L47 21" fill="none" stroke={light ? "#0866FF" : "#FFFFFF"} strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M41 13c6 0 8.5 4.5 8.5 8.5-5 0-8.5-3-8.5-8.5z" fill="#31A24C" />
      </svg>
      {text && <span className={`font-bold tracking-tight text-[20px] ${light ? "text-white" : "text-ink"}`}>VYARTHX</span>}
    </span>
  );
}
