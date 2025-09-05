/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'chat-blue': '#3b82f6',
        'chat-gray': '#f1f5f9',
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}