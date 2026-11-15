export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { forest: "#166534", fresh: "#22C55E", mint: "#D1FAE5", deep: "#1D4ED8", sky: "#38BDF8", cream: "#F8FAF5", ink: "#172B24", amber: "#F59E0B", coral: "#F97373" },
      fontFamily: { sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"] },
      boxShadow: { card: "0 1px 2px rgba(23,43,36,.06), 0 4px 14px rgba(23,43,36,.05)" },
    },
  },
  plugins: [],
};
