"use client"

import { Video, CheckCircle2, Loader2, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"

export type VideoStatus = "analyzing" | "ready" | "error"

interface VideoCardProps {
  title: string
  channel?: string
  duration?: string
  status: VideoStatus
  onClick?: () => void
  className?: string
}

export function VideoCard({ title, channel, duration, status, onClick, className }: VideoCardProps) {
  const getStatusIcon = () => {
    switch (status) {
      case "ready":
        return <CheckCircle2 className="size-4 text-emerald-400" />
      case "analyzing":
        return <Loader2 className="size-4 text-amber-400 animate-spin" />
      case "error":
        return <AlertCircle className="size-4 text-red-400" />
      default:
        return null
    }
  }

  const getStatusText = () => {
    switch (status) {
      case "ready":
        return "Ready"
      case "analyzing":
        return "Analyzing"
      case "error":
        return "Error"
      default:
        return ""
    }
  }

  return (
    <div
      onClick={onClick}
      className={cn(
        "p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:border-violet-500/50 transition-all duration-200 cursor-pointer",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <div className="size-12 rounded-lg bg-gradient-to-br from-violet-600/20 to-purple-600/20 flex items-center justify-center border border-violet-500/30 shrink-0">
          <Video className="size-5 text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-white truncate mb-1">{title}</h4>
          {channel && (
            <p className="text-xs text-slate-400 truncate mb-1">{channel}</p>
          )}
          <div className="flex items-center gap-2 mt-2">
            {getStatusIcon()}
            <span className="text-xs text-slate-500">{getStatusText()}</span>
            {duration && (
              <>
                <span className="text-xs text-slate-500">•</span>
                <span className="text-xs text-slate-500">{duration}</span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

