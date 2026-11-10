/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Strict Palette as Specified in Blueprint
        ivory: {
          50: '#FDFBF7',
          DEFAULT: '#F8F6F0',
          100: '#F2EFE8',
          200: '#E8E3D7',
          300: '#DAD2C2',
        },
        navy: {
          950: '#0B1522',
          900: '#112033',
          DEFAULT: '#172B45',
          800: '#1D3554',
          700: '#26456E',
          600: '#3A6296',
          100: '#E8EEF5',
          50: '#F4F7FA',
        },
        saffron: {
          light: '#FBF5EE',
          50: '#FDF9F5',
          100: '#F8ECE0',
          200: '#F1D7BE',
          DEFAULT: '#D99548',
          vibrant: '#E67E22',
          hover: '#D35400',
          dark: '#B07028',
          900: '#693E10',
        },
        sage: {
          light: '#F1F4F2',
          50: '#F7F9F8',
          100: '#E5ECE7',
          200: '#CBDBD0',
          DEFAULT: '#718575',
          green: '#2E7D32',
          dark: '#56695A',
          900: '#2A362D',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', '"Noto Sans Devanagari"', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        editorial: ['"Playfair Display"', 'Georgia', 'serif'],
      },
      boxShadow: {
        'subtle': '0 1px 3px 0 rgba(23, 43, 69, 0.04), 0 1px 2px -1px rgba(23, 43, 69, 0.02)',
        'premium': '0 8px 30px -4px rgba(23, 43, 69, 0.06), 0 2px 8px -2px rgba(23, 43, 69, 0.03)',
        'float': '0 20px 48px -12px rgba(23, 43, 69, 0.12), 0 8px 16px -4px rgba(23, 43, 69, 0.04)',
        'elevated': '0 30px 60px -15px rgba(23, 43, 69, 0.16)',
        'pill': '0 4px 14px 0 rgba(230, 126, 34, 0.35)',
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
    },
  },
  plugins: [],
};
