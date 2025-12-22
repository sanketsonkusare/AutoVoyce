"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { MoreHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"

export function SharedHeader() {
  const pathname = usePathname()

  return (
    <header className="sticky top-0 z-50 bg-[#0f172a]/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
            <span className="text-white font-semibold text-lg tracking-wide">
              <span className="font-bold">AV</span> AutoVoyce
            </span>
          </Link>

          {/* Navigation */}
          <nav className="flex items-center gap-6">
            <Link
              href="/ingestion"
              className={cn(
                "text-sm font-medium transition-colors",
                pathname === "/ingestion" ? "text-white" : "text-slate-400 hover:text-white",
              )}
            >
              Ingestion
            </Link>
            <Link
              href="/chat"
              className={cn(
                "text-sm font-medium transition-colors",
                pathname === "/chat" ? "text-white" : "text-slate-400 hover:text-white",
              )}
            >
              Chat
            </Link>

            {/* User Avatar */}
            <div className="size-8 rounded-full bg-gradient-to-br from-amber-600 to-amber-800 flex items-center justify-center overflow-hidden">
              <img src="/placeholder-avatar.png" alt="User avatar" className="size-full object-cover" />
            </div>

            {/* More Options */}
            <button className="text-slate-400 hover:text-white transition-colors">
              <MoreHorizontal className="size-5" />
            </button>
          </nav>
        </div>
      </div>
    </header>
  )
}
