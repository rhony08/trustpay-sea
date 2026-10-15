import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        xs: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
        "2xs": "0 1px 1px 0 rgb(0 0 0 / 0.04)",
      },
      blur: {
        xs: "2px",
      },
      colors: {
        trust: {
          navy: "#1E40AF",
          blue: "#2563EB",
        },
      },
    },
  },
  plugins: [],
};

export default config;
