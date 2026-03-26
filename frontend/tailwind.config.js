/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Background colors
        'dark': '#0F0A1E',
        'card': '#1A1333',
        'hover': '#251B47',
        // Primary colors
        'primary': '#8B5CF6',
        'primary-dark': '#7C3AED',
        'primary-light': '#A78BFA',
        // Secondary
        'secondary': '#6D28D9',
        // Accent
        'accent': '#EC4899',
        // Border
        'border-color': '#2D2447',
        // Text colors
        'text-light': '#F9FAFB',
        'text-gray': '#D1D5DB',
        'text-muted': '#9CA3AF',
        // Status colors
        'success': '#10B981',
        'error': '#EF4444',
        'warning': '#F59E0B',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
