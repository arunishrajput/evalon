/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/app/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0a",
        card: "#111111",
        "card-elevated": "#1a1a1a",
        accent: "#3b82f6",
        degraded: "#f59e0b",
        error: "#ef4444",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      keyframes: {
        "fade-in": { from: { opacity: 0 }, to: { opacity: 1 } },
        "zoom-in-95": { from: { opacity: 0, transform: "scale(0.95)" }, to: { opacity: 1, transform: "scale(1)" } },
      },
      animation: {
        "fade-in": "fade-in 0.15s ease-out",
        "zoom-in-95": "zoom-in-95 0.15s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
