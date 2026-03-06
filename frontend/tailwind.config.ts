import type { Config } from 'tailwindcss'

// Extend titan's Tailwind config
const titanConfig = require('@titan-design/react-ui/tailwind.config.js')

const config: Config = {
  content: [
    './src/**/*.{js,jsx,ts,tsx}',
    './node_modules/@titan-design/react-ui/src/**/*.{js,jsx,ts,tsx}',
  ],
  presets: [titanConfig],
  darkMode: 'class',
  theme: {
    extend: {},
  },
  plugins: [],
}

export default config
