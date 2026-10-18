import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { StormBackdrop } from './components/shell/StormBackdrop'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <StormBackdrop />
    <App />
  </StrictMode>,
)
