/** Approved artwork only: full, navigation wordmark, and extracted cyclone. */
const artwork = {
  full: { file: 'foresite-logo-full.png', width: 1200, height: 300, size: 'w-60' },
  compact: { file: 'foresite-wordmark.png', width: 768, height: 166, size: 'w-32' },
  icon: { file: 'foresite-cyclone.png', width: 384, height: 384, size: 'size-8' },
}

export function Brand({
  variant = 'compact',
  className,
  decorative = false,
}: {
  variant?: keyof typeof artwork
  className?: string
  decorative?: boolean
}) {
  const image = artwork[variant]
  return (
    <span
      data-brand={variant}
      className={`inline-block max-w-full shrink-0 align-middle leading-none ${className ?? image.size}`}
    >
      <img
        src={`/${image.file}?v=56ddbbb3`}
        width={image.width}
        height={image.height}
        alt={decorative ? '' : variant === 'full' ? 'FORESITE — Intelligent Worksite Operations' : 'FORESITE'}
        className="block h-auto w-full object-contain"
        decoding="async"
        draggable={false}
      />
    </span>
  )
}
