// Titan Design System
import '@titan-design/react-ui/theme/global.css'
import { applyThemePreset, audiobookPreset } from '@titan-design/react-ui'

// Apply audiobook theme preset
applyThemePreset(audiobookPreset)

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)


