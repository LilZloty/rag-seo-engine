/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      // Example Store Brand Colors
      colors: {
        v07: {
          yellow: '#F7B500',
          yellowHover: '#ffc933',
          yellowMuted: '#d4a000',
          black: '#000000',
          gray: '#808080',
          // Dark palette
          bg: '#000000',
          card: '#111111',
          header: '#1a1a1a',
          surface: '#0a0a0a',
          // Text tiers (WCAG AA on #0a0a0a)
          'text-muted': '#a1a1a1',
          'text-subtle': '#7a7a7a',
        },
        // shadcn chart CSS variable colors
        chart: {
          "1": "hsl(var(--chart-1))",
          "2": "hsl(var(--chart-2))",
          "3": "hsl(var(--chart-3))",
          "4": "hsl(var(--chart-4))",
          "5": "hsl(var(--chart-5))",
        },
      },
      // Typography - Montserrat + Resolve
      fontFamily: {
        sans: ['Montserrat', 'system-ui', 'sans-serif'],
        display: ['Resolve', 'Montserrat', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      // Brand Animations
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out forwards',
        'slide-up': 'slideUp 0.4s ease-out forwards',
        'slide-right': 'slideRight 0.3s ease-out forwards',
        'diagonal-reveal': 'diagonalReveal 0.6s ease-out forwards',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideRight: {
          '0%': { opacity: '0', transform: 'translateX(-12px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        diagonalReveal: {
          '0%': {
            opacity: '0',
            clipPath: 'polygon(0 0, 0 0, 0 100%, 0 100%)'
          },
          '100%': {
            opacity: '1',
            clipPath: 'polygon(0 0, 100% 0, 100% 100%, 0 100%)'
          },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(247, 181, 0, 0)' },
          '50%': { boxShadow: '0 0 20px 2px rgba(247, 181, 0, 0.3)' },
        },
      },
      // 240 degree transforms
      rotate: {
        '240': '240deg',
        '-60': '-60deg', // 240 - 180 = 60, so -60 gives the visual angle
      },
      // Box shadows for industrial aesthetic
      boxShadow: {
        'v07': '0 0 0 1px rgba(247, 181, 0, 0.1)',
        'v07-hover': '0 0 0 1px #F7B500, 0 4px 20px rgba(0, 0, 0, 0.3)',
        'v07-glow': '0 0 20px 2px rgba(247, 181, 0, 0.2)',
      },
      // Background patterns via backdrop
      backgroundImage: {
        'diagonal-lines': 'repeating-linear-gradient(-60deg, transparent, transparent 10px, rgba(247, 181, 0, 0.03) 10px, rgba(247, 181, 0, 0.03) 11px)',
        'grid-pattern': 'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
      },
    },
  },
  plugins: [],
};
