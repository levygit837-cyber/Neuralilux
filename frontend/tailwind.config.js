/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Brand colors
        brand: {
          base: '#0F0A1E',
          card: '#1A1333',
          hover: '#251B47',
          border: '#2D2447',
        },
        // Primary colors
        primary: {
          DEFAULT: '#8B5CF6',
          dark: '#7C3AED',
          light: '#A78BFA',
        },
        // Secondary
        secondary: '#6D28D9',
        // Accent
        accent: '#EC4899',
        // Content colors
        content: {
          light: '#F9FAFB',
          gray: '#D1D5DB',
          muted: '#9CA3AF',
        },
        // Border
        'border-color': '#2D2447',
        // Legacy text colors (mapped to content)
        'text-light': '#F9FAFB',
        'text-gray': '#D1D5DB',
        'text-muted': '#9CA3AF',
        // Legacy background colors (mapped to brand)
        'dark': '#0F0A1E',
        'card': '#1A1333',
        'hover': '#251B47',
        'primary-dark': '#7C3AED',
        'primary-light': '#A78BFA',
        // Status colors
        status: {
          success: '#10B981',
          error: '#EF4444',
          warning: '#F59E0B',
        },
        // Legacy status colors
        'success': '#10B981',
        'error': '#EF4444',
        'warning': '#F59E0B',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        inter: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'glow': '0 0 20px -5px rgba(139, 92, 246, 0.4)',
        'glow-strong': '0 0 25px -2px rgba(139, 92, 246, 0.6)',
        'panel': '4px 0 24px -10px rgba(0, 0, 0, 0.5)',
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
