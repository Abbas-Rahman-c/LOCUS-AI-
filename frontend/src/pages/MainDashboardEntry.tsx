import { DashboardSearch } from '../components/DashboardSearch'
import { DashboardStats } from '../components/DashboardStats'
import { DashboardSources } from '../components/DashboardSources'
import { DashboardCaptures } from '../components/DashboardCaptures'

export default function MainDashboardEntry() {
  return (
    <main className="mx-auto max-w-[1120px] px-8 py-8">
      <DashboardSearch />
      <DashboardStats />

      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.7fr)] gap-5">
        <DashboardSources />
        <DashboardCaptures />
      </div>
    </main>
  )
}
