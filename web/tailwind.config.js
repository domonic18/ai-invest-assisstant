import { panelColors, semanticColors } from './src/theme/colors'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        semantic: {
          rise: semanticColors.rise,
          fall: semanticColors.fall,
        },
        panel: panelColors,
      },
    },
  },
  plugins: [],
}
