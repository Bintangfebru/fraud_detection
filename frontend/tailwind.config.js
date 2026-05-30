/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        // DM Serif Display — editorial headlines (matches Ether UI reference)
        display: ['"DM Serif Display"', 'Georgia', 'serif'],
        // DM Sans — clean body text (matches Ether UI reference)
        body: ['"DM Sans"', 'sans-serif'],
        mono: ['"DM Mono"', 'Consolas', 'monospace'],
      },
      colors: {
        // Liquid glass palette — muted sage/stone base
        glass: {
          50:  'rgba(255,255,255,0.85)',
          100: 'rgba(255,255,255,0.65)',
          200: 'rgba(255,255,255,0.45)',
          300: 'rgba(255,255,255,0.25)',
          400: 'rgba(255,255,255,0.12)',
          500: 'rgba(255,255,255,0.06)',
        },
        // Muted sage green base (like Ether UI background)
        sage: {
          50:  '#f4f6f0',
          100: '#e8ede0',
          200: '#d4ddc8',
          300: '#b8c9a8',
          400: '#8fa876',
          500: '#6b8a55',
          600: '#4d6840',
          700: '#3a5030',
          800: '#2a3c22',
          900: '#1c2a17',
        },
        // Stone/warm neutral
        stone: {
          50:  '#fafaf9',
          100: '#f4f3f0',
          200: '#e8e6e1',
          300: '#d4d0c8',
          400: '#b0ab9e',
          500: '#8a8478',
          600: '#6b6560',
          700: '#4a4642',
          800: '#2e2c29',
          900: '#1a1917',
        },
        // Dark sidebar
        ink: {
          600: '#3d4055',
          700: '#2d3048',
          800: '#1e2138',
          900: '#13162a',
        },
        // Accents
        coral:  { 400: '#E07A5F', 500: '#c8614a' },
        amber:  { 400: '#F2994A', 500: '#d4863a' },
        emerald:{ 400: '#6FCF97', 500: '#45a96a' },
        sky:    { 400: '#56CCF2', 500: '#2fb8e8' },
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
        '4xl': '2rem',
      },
      backdropBlur: {
        xs: '2px',
        sm: '4px',
        md: '12px',
        lg: '20px',
        xl: '40px',
      },
      animation: {
        'fade-in':    'fadeIn 0.4s ease-out',
        'slide-up':   'slideUp 0.4s ease-out',
        'blob-slow':  'blob 12s ease-in-out infinite',
        'blob-slow2': 'blob 15s ease-in-out infinite 3s',
        'blob-slow3': 'blob 18s ease-in-out infinite 6s',
        'pulse-soft': 'pulseSoft 3s ease-in-out infinite',
        'shimmer':    'shimmer 1.8s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        blob: {
          '0%, 100%': { transform: 'translate(0,0) scale(1)' },
          '25%': { transform: 'translate(5%,8%) scale(1.05)' },
          '50%': { transform: 'translate(-4%,5%) scale(0.96)' },
          '75%': { transform: 'translate(6%,-4%) scale(1.03)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
}
