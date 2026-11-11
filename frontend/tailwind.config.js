/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        saathi: {
          orange: '#FF6F00',
          green: '#1B5E20',
          saffron: '#FF9933',
          navy: '#000080',
          blue: '#1E40AF',
          light: '#F8FAFC',
          card: '#FFFFFF',
          border: '#E2E8F0',
        }
      }
    },
  },
  plugins: [],
}
