// Meta-style design tokens. Names are kept from the original palette so every page picks them up:
// forest = primary accent, fresh = success, mint = selected/hover tint, cream = app background, ink = text.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forest: "#0866FF", // primary (Meta blue)
        fresh: "#31A24C", // success green
        mint: "#E7F3FF", // selected / hover tint
        deep: "#0866FF",
        sky: "#45BD62",
        cream: "#F0F2F5", // app background
        ink: "#050505", // primary text (use /60 for secondary #65676B-ish)
        amber: "#F7B928",
        coral: "#F02849",
        line: "#CED0D4", // dividers
        hover: "#F2F2F2", // list hover
        btn: "#E4E6EB", // secondary button
      },
      fontFamily: { sans: ["Segoe UI Historic", "Segoe UI", "Helvetica", "Arial", "system-ui", "sans-serif"] },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,.2)",
        pop: "0 12px 28px 0 rgba(0,0,0,.2), 0 2px 4px 0 rgba(0,0,0,.1)",
        nav: "0 1px 2px rgba(0,0,0,.1), 0 2px 4px rgba(0,0,0,.05)",
      },
    },
  },
  plugins: [],
};
