"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { UserButton } from "@clerk/nextjs"
import { cn } from "@/lib/utils"

const NAV = [
  {
    group: "Core",
    items: [
      { label: "Command Center", href: "/dashboard", icon: "⬡" },
      { label: "Intelligence Feed", href: "/intelligence", icon: "◈" },
      { label: "Date Explorer", href: "/explore", icon: "◷" },
    ],
  },
  {
    group: "Rankings",
    items: [
      { label: "Top Picks", href: "/picks", icon: "↑", badge: "30", badgeColor: "green" as const },
      { label: "Avoid List", href: "/avoid", icon: "↓", badge: "30", badgeColor: "red" as const },
      { label: "Halal Screen", href: "/halal", icon: "☽" },
      { label: "Watchlist", href: "/watchlist", icon: "◇" },
    ],
  },
  {
    group: "Tools",
    items: [
      { label: "AI Chat", href: "/chat", icon: "◎" },
      { label: "Data Sources", href: "/sources", icon: "◈" },
    ],
  },
  {
    group: "Account",
    items: [{ label: "Profile & Goals", href: "/profile", icon: "○" }],
  },
]

export function Sidebar() {
  const path = usePathname()

  return (
    <aside className="w-[210px] flex-shrink-0 bg-[#080808] border-r border-[#161616] flex flex-col h-screen sticky top-0 overflow-hidden">
      <div className="px-5 pt-5 pb-1">
        <div className="text-sm font-bold tracking-[0.14em] uppercase text-white font-sans">
          ARGUS
        </div>
        <div className="text-[10px] tracking-[0.18em] uppercase text-[#2d2d2d] mt-0.5">
          Intelligence Platform
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-4">
        {NAV.map((group) => (
          <div key={group.group}>
            <div className="text-[9px] tracking-[0.16em] uppercase font-bold text-[#2d2d2d] px-2 mb-1">
              {group.group}
            </div>
            {group.items.map((item) => {
              const active =
                path === item.href || path.startsWith(item.href + "/")
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs transition-colors border-l-2 mb-0.5",
                    active
                      ? "bg-[#111] text-white border-[#e2e8f0]"
                      : "text-[#4b5563] border-transparent hover:text-[#94a3b8]"
                  )}
                >
                  <span className="w-3 text-center text-[10px] flex-shrink-0">
                    {item.icon}
                  </span>
                  <span className="flex-1 truncate">{item.label}</span>
                  {"badge" in item && item.badge && (
                    <span
                      className={cn(
                        "text-[9px] px-1.5 py-0.5 rounded border flex-shrink-0",
                        item.badgeColor === "green"
                          ? "bg-[#051208] text-[#22c55e] border-[#0a2810]"
                          : "bg-[#140305] text-[#ef4444] border-[#280510]"
                      )}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="px-3 pb-4 flex-shrink-0">
        <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <UserButton />
            <div className="min-w-0">
              <div className="text-xs font-semibold text-white truncate">
                Account
              </div>
              <div className="text-[10px] text-[#4b5563] truncate">
                Moderate · Long-term
              </div>
            </div>
          </div>
          <div className="flex gap-1.5 flex-wrap">
            <div className="text-[10px] bg-[#111] border border-[#1c1c1c] rounded px-1.5 py-0.5 text-[#4b5563]">
              Budget{" "}
              <span className="text-[#e2e8f0] font-semibold">$25K</span>
            </div>
            <div className="text-[10px] bg-[#111] border border-[#1c1c1c] rounded px-1.5 py-0.5 text-[#4b5563]">
              ☽ <span className="text-[#22c55e] font-semibold">On</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
