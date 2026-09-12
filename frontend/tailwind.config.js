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
          0: '#F8FAFC',
          1: '#FFFFFF',
          2: '#F1F5F9',
          3: '#E2E8F0',
        },
        risk: {
          low: '#16A34A',
          medium: '#CA8A04',
          high: '#C2410C', // deeper orange-red
          critical: '#DC2626',
          offline: '#64748B',
        },
      },
    },
  },
  plugins: [],
}
