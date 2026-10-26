/** Shared UI pieces. Warm, menu-like, but the data colours stay strict. */

const SENTIMENT_STYLE = {
  positive: { bg: 'var(--positive-soft)', fg: '#1c5cab', dot: 'var(--positive)', label: 'Positive' },
  neutral: { bg: 'var(--neutral-soft)', fg: 'var(--text-secondary)', dot: 'var(--neutral)', label: 'Neutral' },
  negative: { bg: 'var(--negative-soft)', fg: '#8f2b20', dot: 'var(--negative)', label: 'Negative' },
}

const URGENCY_STYLE = {
  low: { bg: 'var(--neutral-soft)', fg: 'var(--text-secondary)', icon: '○', label: 'Low' },
  medium: { bg: 'var(--brass-soft)', fg: '#7a5410', icon: '◑', label: 'Medium' },
  high: { bg: 'var(--clay-soft)', fg: '#8f2b20', icon: '◉', label: 'High' },
}

export function SentimentBadge({ value }) {
  const style = SENTIMENT_STYLE[value] || SENTIMENT_STYLE.neutral
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
      style={{ background: style.bg, color: style.fg }}
    >
      <span className="inline-block h-2 w-2 rounded-full"
            style={{ background: style.dot }} aria-hidden="true" />
      {style.label}
    </span>
  )
}

/** Urgency always ships icon + word, never colour alone. */
export function UrgencyBadge({ value }) {
  const style = URGENCY_STYLE[value] || URGENCY_STYLE.low
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
      style={{ background: style.bg, color: style.fg }}
    >
      <span aria-hidden="true">{style.icon}</span>
      {style.label} urgency
    </span>
  )
}

export function Card({ title, subtitle, action, children, className = '', padded = true }) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b px-6 py-4 hairline">
          <div>
            {title && <h2 className="display text-base font-semibold">{title}</h2>}
            {subtitle && (
              <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>{subtitle}</p>
            )}
          </div>
          {action}
        </header>
      )}
      <div className={padded ? 'p-6' : ''}>{children}</div>
    </section>
  )
}

export function StatTile({ label, value, hint, accent, icon }) {
  return (
    <div className="card card-hover px-5 py-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em]"
           style={{ color: 'var(--text-muted)' }}>
          {label}
        </p>
        {icon && <span aria-hidden="true" className="text-base opacity-40">{icon}</span>}
      </div>
      <p className="display mt-2 text-[2rem] leading-none font-semibold"
         style={{ color: accent || 'var(--text-primary)' }}>
        {value}
      </p>
      {hint && (
        <p className="mt-2 text-xs" style={{ color: 'var(--text-secondary)' }}>{hint}</p>
      )}
    </div>
  )
}

export function Spinner({ label = 'Loading' }) {
  return (
    <div className="flex items-center gap-3 py-10 text-sm" style={{ color: 'var(--text-secondary)' }}>
      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
            aria-hidden="true" />
      {label}…
    </div>
  )
}

export function ErrorNote({ error, onRetry }) {
  if (!error) return null
  return (
    <div role="alert" className="rounded-xl px-4 py-3 text-sm"
         style={{ background: 'var(--clay-soft)', color: '#8f2b20' }}>
      <p className="font-medium">Something went wrong</p>
      <p className="mt-0.5">{error.message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-xs font-medium underline">Try again</button>
      )}
    </div>
  )
}

export function EmptyNote({ children }) {
  return (
    <p className="py-10 text-center text-sm" style={{ color: 'var(--text-muted)' }}>{children}</p>
  )
}

export function Button({ variant = 'primary', className = '', ...props }) {
  const base =
    'inline-flex items-center justify-center rounded-full px-5 py-2.5 text-sm font-medium ' +
    'transition disabled:cursor-not-allowed disabled:opacity-50'
  const styles = {
    primary: { background: 'var(--herb)', color: 'var(--on-brand)' },
    ghost: { background: 'transparent', color: 'var(--text-secondary)',
             border: '1px solid var(--hairline)' },
  }
  const hover = variant === 'primary' ? 'hover:opacity-90' : 'hover:bg-black/[0.03]'
  return <button className={`${base} ${hover} ${className}`} style={styles[variant]} {...props} />
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold tracking-wide"
            style={{ color: 'var(--text-secondary)' }}>
        {label}
      </span>
      {children}
      {hint && (
        <span className="mt-1 block text-xs" style={{ color: 'var(--text-muted)' }}>{hint}</span>
      )}
    </label>
  )
}

export const inputClass =
  'w-full rounded-xl border px-3.5 py-2.5 text-sm outline-none hairline ' +
  'bg-white/70 focus:bg-white focus:border-[#1d6142] focus:ring-2 focus:ring-[#1d6142]/15 ' +
  'transition placeholder:text-[#8a9b8f]'

export const ASPECT_LABELS = {
  food_quality: 'Food quality',
  service: 'Service',
  staff_behaviour: 'Staff behaviour',
  waiting_time: 'Waiting time',
  price: 'Price',
  portion_size: 'Portion size',
  cleanliness: 'Cleanliness',
  ambience: 'Ambience',
  delivery: 'Delivery',
  packaging: 'Packaging',
}

/** A small glyph per aspect - decorative, always paired with the word. */
export const ASPECT_ICONS = {
  food_quality: '🍽',
  service: '🛎',
  staff_behaviour: '👤',
  waiting_time: '⏱',
  price: '💰',
  portion_size: '⚖',
  cleanliness: '✦',
  ambience: '🕯',
  delivery: '🛵',
  packaging: '📦',
}

export const prettyAspect = (key) =>
  ASPECT_LABELS[key] || key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

export function Stars({ value, size = 'text-sm' }) {
  if (!value) return null
  return (
    <span className={size} aria-label={`${value} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} style={{ color: n <= value ? 'var(--brass)' : 'var(--gridline)' }}
              aria-hidden="true">★</span>
      ))}
    </span>
  )
}
