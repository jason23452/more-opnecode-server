import { HeroUIProvider } from '@heroui/react'
import { BrowserRouter } from 'react-router-dom'
import { AppRouter } from '@/App/Router/AppRouter'

export function MainApp() {
  return (
    <HeroUIProvider>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </HeroUIProvider>
  )
}
