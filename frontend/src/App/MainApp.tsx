import { HeroUIProvider } from '@heroui/react'
import { RouterProvider } from 'react-router-dom'
import { AppRouter } from '@/App/Router/AppRouter'

export function MainApp() {
  return (
    <HeroUIProvider>
      <RouterProvider router={AppRouter} />
    </HeroUIProvider>
  )
}
