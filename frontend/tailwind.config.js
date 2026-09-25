/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#21295C",
        deepblue: "#065A82",
        teal: "#1C7293",
        amber: "#F2A65A",
        ink: "#0E2233",
      },
    },
  },
  plugins: [],
};
