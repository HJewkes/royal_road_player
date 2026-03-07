import type { Config } from 'tailwindcss'

// Use titan's Tailwind config as a preset, but strip nativewind/preset
// since audiobook is web-only and we need CSS variables to remain as var() references
// (nativewind resolves them at build time for React Native compatibility)
const titanConfig = require('@titan-design/react-ui/tailwind.config.js')
const { presets: _nativewind, ...titanWithoutNativewind } = titanConfig

const config: Config = {
  content: [
    './src/**/*.{js,jsx,ts,tsx}',
    './node_modules/@titan-design/react-ui/src/**/*.{js,jsx,ts,tsx}',
  ],
  presets: [titanWithoutNativewind],
  darkMode: 'class',
  theme: {
    extend: {},
  },
  plugins: [],
}

export default config
