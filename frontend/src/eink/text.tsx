import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/700.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { TextPageDisplay } from './TextPageDisplay'
import './eink.css'

createRoot(document.getElementById('text-root')!).render(
  <StrictMode>
    <TextPageDisplay />
  </StrictMode>,
)
