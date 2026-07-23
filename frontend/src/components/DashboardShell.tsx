import { Outlet } from 'react-router-dom'
import { DashboardNav } from './DashboardNav'

export function DashboardShell() {
  return (
    <div className="min-h-screen bg-[#F7F7FA]">
      <DashboardNav />
      <Outlet />
    </div>
  )
}
