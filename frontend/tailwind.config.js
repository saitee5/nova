/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#FFF7ED',
          100: '#FFEDD5',
          200: '#FED7AA',
          300: '#FDBA74',
          400: '#FB923C',
          500: '#F97316', // Primary Brand Accent
          600: '#EA580C',
          700: '#C2410C',
          800: '#9A3412',
          900: '#7C2D12',
        },
        surface: {
          0: '#F8F9FA', // Page Background
          1: '#FFFFFF', // Card Surface
          2: '#F1F5F9', // Subtle section / elevated
          3: '#E2E8F0', // Border
        },
        risk: {
          low: '#16A34A',
          medium: '#CA8A04',
          high: '#C2410C',
          critical: '#DC2626',
          offline: '#64748B',
        },
        kpi: {
          navy: '#1E293B',
          teal: '#4A7C7C',
          gray: '#94A3B8',
          gold: '#C9A227',
        },
      },
      fontFamily: {
        sans: ['"Titillium Web"', 'sans-serif'],
        heading: ['"Archivo Black"', 'sans-serif'],
        subheading: ['"Bebas Neue"', 'sans-serif'],
        display: ['"Bebas Neue"', '"Archivo Black"', 'sans-serif'],
        bebas: ['"Bebas Neue"', 'sans-serif'],
        archivo: ['"Archivo Black"', 'sans-serif'],
        titillium: ['"Titillium Web"', 'sans-serif'],
        mono: ['"Roboto Mono"', 'monospace'],
        slab: ['"Roboto Slab"', 'serif'],
        saira: ['"Saira"', 'sans-serif'],
        doppio: ['"Doppio One"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
