import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Deployed environment: Route relative /api/* requests to Render Django backend
const apiBase = import.meta.env.VITE_API_BASE_URL;
if (apiBase && typeof window !== 'undefined') {
  const withProtocol = apiBase.startsWith('http://') || apiBase.startsWith('https://') 
    ? apiBase 
    : `https://${apiBase}`;
  const normalizedBase = withProtocol.replace(/\/api(\/v1)?\/?$/, '').replace(/\/$/, '');
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === 'string' && input.startsWith('/api/')) {
      return originalFetch(`${normalizedBase}${input}`, init);
    }
    if (input instanceof Request && input.url.startsWith('/api/')) {
      return originalFetch(new Request(`${normalizedBase}${input.url}`, input), init);
    }
    return originalFetch(input, init);
  };
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
