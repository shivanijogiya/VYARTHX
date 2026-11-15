import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import L from "leaflet";

export type Marker = { lat: number; lng: number; color?: string; label?: string; radius?: number };
export default function MapView({ markers, height = 380, center = [13.0827, 80.2707] as [number, number], zoom = 11, polylines = [] }: { markers: Marker[]; height?: number; center?: [number, number]; zoom?: number; polylines?: { points: [number, number][]; color?: string }[] }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  useEffect(() => {
    if (!el.current || map.current) return;
    map.current = L.map(el.current, { scrollWheelZoom: false }).setView(center, zoom);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => { map.current?.remove(); map.current = null; };
  }, []);
  useEffect(() => {
    if (!map.current || !layer.current) return;
    layer.current.clearLayers();
    markers.forEach((m) => {
      L.circleMarker([m.lat, m.lng], { radius: m.radius || 8, color: "#fff", weight: 2, fillColor: m.color || "#166534", fillOpacity: 0.9 }).bindPopup(m.label || "").addTo(layer.current!);
    });
    polylines.forEach((p) => L.polyline(p.points, { color: p.color || "#1D4ED8", weight: 4, opacity: 0.8 }).addTo(layer.current!));
    const pts = [...markers.map((m) => [m.lat, m.lng] as [number, number]), ...polylines.flatMap((p) => p.points)];
    if (pts.length > 1) map.current.fitBounds(L.latLngBounds(pts).pad(0.15));
  }, [markers, polylines]);
  return <div ref={el} style={{ height }} className="w-full border border-green-900/10 rounded-xl overflow-hidden" role="img" aria-label="Map" />;
}
