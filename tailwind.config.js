/** @type {import('tailwindcss').Config} */
const colors = require('tailwindcss/colors');

module.exports = {
  content: ['./app/templates/**/*.html', './app/static/js/**/*.js'],
  darkMode: 'class',
  // Alliance colors in the live-status template are assembled dynamically.
  safelist: [{pattern: /^(bg|text|border)-(red|blue)-(100|500|800)$/}],
  theme: {
    extend: {
      // One neutral palette everywhere: existing gray-* classes render as zinc
      colors: {gray: colors.zinc},
    },
  },
  plugins: [],
};
