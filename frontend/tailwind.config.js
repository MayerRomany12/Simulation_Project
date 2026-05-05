/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0f172a',
        surface: 'rgba(30, 41, 59, 0.7)',
        primary: '#38bdf8',
        secondary: '#818cf8',
        accent: '#f472b6',
        success: '#34d399',
        warning: '#fbbf24',
        danger: '#f87171',
      },
    },
  },
  plugins: [],
}
