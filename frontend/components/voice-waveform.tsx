"use client"

import { cn } from "@/lib/utils"

interface VoiceWaveformProps {
  isActive?: boolean
  className?: string
  barCount?: number
}

export function VoiceWaveform({ isActive = false, className, barCount = 7 }: VoiceWaveformProps) {
  return (
    <div className={cn("flex items-center gap-1", className)}>
      {Array.from({ length: barCount }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "w-1 bg-gradient-to-t from-violet-500 to-purple-500 rounded-full transition-all",
            isActive ? "animate-pulse" : "opacity-30"
          )}
          style={{
            height: isActive ? `${20 + Math.random() * 30}px` : "8px",
            animationDelay: `${i * 100}ms`,
            animationDuration: `${800 + Math.random() * 400}ms`,
          }}
        />
      ))}
    </div>
  )
}

