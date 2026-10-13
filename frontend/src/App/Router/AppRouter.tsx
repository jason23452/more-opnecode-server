import { Route, Routes } from 'react-router-dom'
import { ContainerDashboard } from '@/Features/Containers/Pages/ContainerDashboard'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<ContainerDashboard />} />
      <Route path="/containers/create" element={<ContainerDashboard />} />
    </Routes>
  )
}
