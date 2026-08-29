/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        base: {
          950: "#121212",
          900: "#1a1a1a",
          850: "#212121",
          800: "#262626",
          700: "#333333",
          600: "#4d4d4d",
          500: "#6b6b6b",
          400: "#8f8f8f",
          300: "#b3b3b3",
        },
        orange: {
          DEFAULT: "#FF6B35",
          50: "#fff1ec",
          400: "#ff8a5e",
          500: "#FF6B35",
          600: "#e5501c",
          700: "#c23e12",
        },
        cyan: {
          DEFAULT: "#00D9FF",
          50: "#e5fbff",
          400: "#3ee4ff",
          500: "#00D9FF",
          600: "#00a8c7",
          700: "#00819a",
        },
        positive: "#22c55e",
        negative: "#ef4444",
      },
      boxShadow: {
        glow: "0 0 24px -4px rgba(255,107,53,0.35)",
        "glow-cyan": "0 0 24px -4px rgba(0,217,255,0.35)",
      },
    },
  },
  plugins: [],
};
