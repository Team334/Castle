/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/templates/**/*.html', './app/static/js/**/*.js'],
  darkMode: 'class',
  // Alliance colors in the live-status template are assembled dynamically.
  safelist: [{pattern: /^(bg|text|border)-(red|blue)-(100|500|800)$/}],
  theme: {extend: {}},
  plugins: [],
};
