/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: {
          bg: '#050505',
          panel: '#111111',
          sidebar: '#151515',
          border: '#292929',
          accent: '#FFD83D',
          'accent-hover': '#F5C842'
        }
      }
    },
  },
  plugins: [],
}