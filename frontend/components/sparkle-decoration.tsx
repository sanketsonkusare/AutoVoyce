export function SparkleDecoration() {
  return (
    <div className="fixed bottom-8 right-8 pointer-events-none">
      <svg
        width="48"
        height="48"
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="opacity-30"
      >
        <path d="M24 0L26.4 21.6L48 24L26.4 26.4L24 48L21.6 26.4L0 24L21.6 21.6L24 0Z" fill="url(#sparkle-gradient)" />
        <defs>
          <linearGradient id="sparkle-gradient" x1="0" y1="0" x2="48" y2="48">
            <stop stopColor="#64748b" />
            <stop offset="1" stopColor="#475569" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  )
}
