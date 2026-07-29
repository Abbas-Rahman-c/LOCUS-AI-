export function LocusLogo({
  className = '',
  variant = 'dark',
  size = 30,
}: {
  className?: string
  variant?: 'dark' | 'light'
  size?: number
}) {
  const textColor = variant === 'light' ? 'text-white' : 'text-black'

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <img
        src="/locus-mark.png"
        alt=""
        width={size}
        height={size}
        className="shrink-0 rounded-[6px]"
        style={{ width: size, height: size }}
      />
      <span className={`text-[14px] font-bold tracking-[0.04em] ${textColor}`}>
        LOCUS <span className="text-[#5b52e8]">AI</span>
      </span>
    </div>
  )
}
