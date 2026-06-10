import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const rootElement: HTMLElement | null = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found — cannot mount application');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Register service worker after app mount (CSP-compliant: no inline scripts)
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error: Error) => {
      console.error('Service worker registration failed:', error);
    });
  });
}
