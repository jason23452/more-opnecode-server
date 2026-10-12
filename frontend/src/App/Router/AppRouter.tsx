import { createBrowserRouter } from 'react-router-dom'
import { HomePage } from '@/Features/Home/Pages/HomePage'

export const AppRouter = createBrowserRouter([
  {
    path: '/',
    element: <HomePage />,
  },
])
