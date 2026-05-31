import { Suspense } from "react"
import { IntelligenceClient } from "./client"

export default function IntelligencePage() {
  return (
    <Suspense fallback={<div className="p-6 text-[#2d2d2d] text-xs">Loading...</div>}>
      <IntelligenceClient />
    </Suspense>
  )
}
