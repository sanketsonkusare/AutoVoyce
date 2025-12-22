import { Heart } from "lucide-react"

export function SharedFooter() {
  return (
    <footer className="px-6 py-4 border-t border-slate-700/30">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <p>© 2025 AutoVoyce. All rights reserved.</p>
        <div className="flex items-center gap-1">
          <span>Made with</span>
          <Heart className="size-3 fill-red-500 text-red-500" />
          <span>by AutoVoyce Team</span>
        </div>
      </div>
    </footer>
  )
}
