/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./pages/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: { extend: { fontFamily: { naskh: ['var(--font-naskh)', 'Noto Naskh Arabic', 'serif'] } } },
  plugins: [require('@tailwindcss/forms')],
};
