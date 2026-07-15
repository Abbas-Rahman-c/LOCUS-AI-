export function LocusLogo({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-[6px] bg-black">
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M8 2.5L12.33 10H3.67L8 2.5Z"
            fill="white"
            transform="rotate(0 8 8)"
          />
          <path
            d="M8 2.5L12.33 10H3.67L8 2.5Z"
            fill="white"
            transform="rotate(120 8 8)"
          />
          <path
            d="M8 2.5L12.33 10H3.67L8 2.5Z"
            fill="white"
            transform="rotate(240 8 8)"
          />
        </svg>
      </div>
      <span className="text-[14px] font-bold tracking-[0.04em] text-black">
        LOCUS AI
      </span>
    </div>
  )
}
