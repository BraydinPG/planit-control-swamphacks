import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import { AuthCheckPage } from './AuthCheckPage'
import { AuthProvider } from './AuthProvider'

// Entry for frontend/auth-check.html. Auth0 returns here, so add
// http://localhost:5173/auth-check.html to the Allowed Callback URLs.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider redirectUri={`${window.location.origin}/auth-check.html`}>
      <AuthCheckPage />
    </AuthProvider>
  </StrictMode>,
)
