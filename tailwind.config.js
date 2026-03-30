/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        nova: {
          purple: '#7C3AED',
          blue:   '#3B82F6',
          pink:   '#EC4899',
          orange: '#F97316',
          cyan:   '#06B6D4',
        },
      },
      keyframes: {
        'border-flow': {
          '0%':   { backgroundPosition: '0% 50%' },
          '50%':  { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        pulse: {
          '0%, 100%': { opacity: '0.6' },
          '50%':      { opacity: '1' },
        },
      },
      animation: {
        'border-flow':        'border-flow 4s ease infinite',
        'border-flow-fast':   'border-flow 1.2s ease infinite',
        'pulse-slow':         'pulse 2.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
