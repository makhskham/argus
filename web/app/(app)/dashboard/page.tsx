import { Suspense } from "react"
import { DashboardClient } from "./client"

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="p-6 text-[#2d2d2d] text-xs">Loading...</div>}>
      <DashboardClient />
    </Suspense>
  )
}
