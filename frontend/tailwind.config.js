/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        canvas: 'var(--canvas)',
        workspace: 'var(--workspace)',
        surface: 'var(--surface)',
        border: 'var(--border)',
        success: 'var(--success)',
        warning: 'var(--warning)',
        critical: 'var(--critical)',
        info: 'var(--info)',
      },
      transitionDuration: {
        product: '180ms',
      },
    },
  },
  plugins: [],
};
