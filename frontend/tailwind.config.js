/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          base: "rgb(var(--color-brand-base) / <alpha-value>)",
          deep: "rgb(var(--color-brand-deep) / <alpha-value>)",
          card: "rgb(var(--color-brand-card) / <alpha-value>)",
          hover: "rgb(var(--color-brand-hover) / <alpha-value>)",
          border: "rgb(var(--color-brand-border) / <alpha-value>)",
          line: "rgb(var(--color-brand-line) / <alpha-value>)",
        },
        primary: {
          DEFAULT: "rgb(var(--color-primary) / <alpha-value>)",
          dark: "rgb(var(--color-primary-dark) / <alpha-value>)",
          light: "rgb(var(--color-primary-light) / <alpha-value>)",
          soft: "rgb(var(--color-primary-soft) / <alpha-value>)",
          pale: "rgb(var(--color-primary-pale) / <alpha-value>)",
          deep: "rgb(var(--color-primary-deep) / <alpha-value>)",
          strong: "rgb(var(--color-primary-strong) / <alpha-value>)",
          edge: "rgb(var(--color-primary-edge) / <alpha-value>)",
        },
        secondary: "rgb(var(--color-secondary) / <alpha-value>)",
        accent: "rgb(var(--color-accent) / <alpha-value>)",
        content: {
          light: "rgb(var(--color-content-light) / <alpha-value>)",
          soft: "rgb(var(--color-content-soft) / <alpha-value>)",
          gray: "rgb(var(--color-content-gray) / <alpha-value>)",
          subtle: "rgb(var(--color-content-subtle) / <alpha-value>)",
          muted: "rgb(var(--color-content-muted) / <alpha-value>)",
        },
        status: {
          success: "rgb(var(--color-status-success) / <alpha-value>)",
          error: "rgb(var(--color-status-error) / <alpha-value>)",
          warning: "rgb(var(--color-status-warning) / <alpha-value>)",
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(circle, var(--tw-gradient-stops))",
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        inter: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'glow': '0 0 20px -5px rgba(139, 92, 246, 0.4)',
        'glow-strong': '0 0 25px -2px rgba(139, 92, 246, 0.6)',
        'panel': '4px 0 24px -10px rgba(0, 0, 0, 0.5)',
        "glow-primary": "0 0 10px rgb(var(--color-primary))",
        "glow-success": "0 0 5px rgb(var(--color-status-success))",
        "active-bar": "inset 4px 0 0 0 rgb(var(--color-primary))",
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'fade-in': 'fadeIn 0.4s ease-out forwards',
        'pulse-ring': 'pulse-ring 2s infinite',
        'typing-dot': 'typing-dot 1.2s infinite ease-in-out',
        'blink': 'cursor-blink 1s step-end infinite',
        'spin-slow': 'spin-slow 3s linear infinite',
      },
      keyframes: {
        'cursor-blink': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        'spin-slow': {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.8)', boxShadow: '0 0 0 0 rgba(16, 185, 129, 0.7)' },
          '70%': { transform: 'scale(1)', boxShadow: '0 0 0 4px rgba(16, 185, 129, 0)' },
          '100%': { transform: 'scale(0.8)', boxShadow: '0 0 0 0 rgba(16, 185, 129, 0)' },
        },
        'typing-dot': {
          '0%, 20%': { transform: 'translateY(0)', opacity: '0.5' },
          '50%': { transform: 'translateY(-4px)', opacity: '1' },
          '80%, 100%': { transform: 'translateY(0)', opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
}
