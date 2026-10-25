import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { AspectChart, BranchChart, SentimentSplit, TrendChart } from '../charts/charts'
import {
  ASPECT_ICONS, Card, EmptyNote, ErrorNote, Spinner, StatTile, UrgencyBadge, prettyAspect,
} from '../components/ui'

const RANGES = [
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '1 year', days: 365 },
]

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export default function Dashboard() {
  const [days, setDays] = useState(90)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Fire them together - five sequential round trips is a visibly slower page
      const [summary, trends, aspects, branches, alerts] = await Promise.all([
        api.summary(),
        api.trends({ days }),
        api.aspects(),
        api.branches(),
        api.alerts({ limit: 5 }),
      ])
      setData({ summary, trends, aspects, branches, alerts })
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => { load() }, [load])

  if (loading && !data) return <Spinner label="Setting the table" />
  if (error) return <ErrorNote error={error} onRetry={load} />
  if (!data) return null

  const { summary, trends, aspects, branches, alerts } = data
  const analysed = summary.analysed_reviews || 0
  const negativeShare = analysed ? Math.round((summary.sentiment.negative / analysed) * 100) : 0
  const urgent = summary.high_urgency_open

  return (
    <div className="space-y-7">

      {/* --- masthead */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.16em]" style={{ color: 'var(--text-muted)' }}>
            {greeting()}
          </p>
          <h1 className="display mt-1.5 text-3xl font-semibold">Front of house</h1>
          <p className="mt-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
            {summary.total_reviews} guest reviews collected · {analysed} analysed
          </p>
        </div>

        <div className="flex items-center gap-1 rounded-full border p-1 hairline"
             style={{ background: 'var(--surface-1)' }}>
          {RANGES.map((range) => (
            <button
              key={range.days}
              onClick={() => setDays(range.days)}
              className="rounded-full px-3.5 py-1.5 text-xs font-medium transition"
              style={days === range.days
                ? { background: 'var(--herb)', color: '#fffdf8' }
                : { color: 'var(--text-secondary)' }}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* --- Urgent first. A manager needs to know about raw chicken before
             they need to know the sentiment split. */}
      <section
        className="overflow-hidden rounded-[14px] border"
        style={{
          borderColor: urgent > 0 ? 'rgba(168,70,47,0.28)' : 'var(--hairline)',
          background: 'var(--surface-1)',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <header
          className="flex items-center justify-between gap-4 border-b px-6 py-4"
          style={{
            borderColor: 'var(--hairline)',
            background: urgent > 0 ? 'var(--clay-soft)' : 'transparent',
          }}
        >
          <div className="flex items-center gap-3">
            <span
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm"
              style={{
                background: urgent > 0 ? 'var(--clay)' : 'var(--surface-2)',
                color: urgent > 0 ? '#fffdf8' : 'var(--text-muted)',
              }}
              aria-hidden="true"
            >
              {urgent > 0 ? '!' : '✓'}
            </span>
            <div>
              <h2 className="display text-base font-semibold">
                {urgent > 0 ? 'Needs attention now' : 'Nothing urgent'}
              </h2>
              <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                Food safety, billing disputes and staff conduct are escalated automatically
              </p>
            </div>
          </div>
          <Link to="/reviews?urgency=high" className="shrink-0 text-xs font-medium underline"
                style={{ color: 'var(--text-secondary)' }}>
            View all
          </Link>
        </header>

        {alerts.length === 0 ? (
          <EmptyNote>All complaints are routine. Nothing needs escalating.</EmptyNote>
        ) : (
          <ul className="divide-y" style={{ borderColor: 'var(--hairline)' }}>
            {alerts.map((review) => (
              <li key={review.review_id}
                  className="flex items-start gap-4 px-6 py-4 transition hover:bg-black/[0.015]">
                <div className="min-w-0 flex-1">
                  <p className="text-sm leading-relaxed">{review.review_text}</p>
                  <p className="mt-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {review.review_date} · {review.prediction?.urgency_reason || 'flagged for review'}
                  </p>
                </div>
                <UrgencyBadge value="high" />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* --- the numbers */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Guest reviews" value={summary.total_reviews} icon="✉" />
        <StatTile
          label="Urgent"
          value={urgent}
          icon="!"
          accent={urgent > 0 ? 'var(--clay)' : undefined}
          hint={urgent > 0 ? 'Needs a response today' : 'Nothing outstanding'}
        />
        <StatTile
          label="Negative share"
          value={`${negativeShare}%`}
          icon="◔"
          hint={`${summary.sentiment.negative} of ${analysed} analysed`}
        />
        <StatTile
          label="Average rating"
          value={summary.average_star_rating ?? '—'}
          icon="★"
          accent={summary.average_star_rating ? 'var(--brass)' : undefined}
          hint={summary.average_star_rating ? 'out of 5 stars' : 'No ratings given'}
        />
      </div>

      {/* --- sentiment + complaints */}
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card title="How guests feel" subtitle="Across every analysed review">
          <SentimentSplit counts={summary.sentiment} />
        </Card>

        <Card title="What they complain about"
              subtitle="Aspects mentioned negatively, most frequent first">
          <AspectChart data={aspects} />
        </Card>
      </div>

      <Card title="Sentiment over time" subtitle={`Daily, last ${days} days`}>
        <TrendChart data={trends} />
      </Card>

      {/* --- branches + aspect detail */}
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <Card title="Across the branches" subtitle="Share of reviews that are negative">
          <BranchChart data={branches} />
        </Card>

        <Card title="Every aspect" subtitle="Positive and negative mentions side by side"
              padded={false}>
          {aspects.length === 0 ? (
            <EmptyNote>No aspects detected yet.</EmptyNote>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-[11px] uppercase tracking-wide hairline"
                      style={{ color: 'var(--text-muted)' }}>
                    <th className="px-6 py-3 text-left font-semibold">Aspect</th>
                    <th className="px-3 py-3 text-right font-semibold">Positive</th>
                    <th className="px-3 py-3 text-right font-semibold">Negative</th>
                    <th className="px-6 py-3 text-right font-semibold">Negative</th>
                  </tr>
                </thead>
                <tbody>
                  {aspects.map((row) => (
                    <tr key={row.aspect}
                        className="border-b last:border-0 hairline transition hover:bg-black/[0.015]">
                      <td className="px-6 py-3">
                        <span className="mr-2 opacity-60" aria-hidden="true">
                          {ASPECT_ICONS[row.aspect] || '•'}
                        </span>
                        {prettyAspect(row.aspect)}
                      </td>
                      <td className="tabular px-3 py-3 text-right"
                          style={{ color: 'var(--text-secondary)' }}>{row.positive}</td>
                      <td className="tabular px-3 py-3 text-right"
                          style={{ color: 'var(--text-secondary)' }}>{row.negative}</td>
                      <td className="px-6 py-3 text-right">
                        <span className="inline-flex items-center gap-2">
                          <span className="h-1.5 w-14 overflow-hidden rounded-full"
                                style={{ background: 'var(--gridline)' }}>
                            <span className="block h-full rounded-full"
                                  style={{ width: `${row.negative_share * 100}%`,
                                           background: 'var(--negative)' }} />
                          </span>
                          <span className="tabular w-9 text-right font-medium">
                            {Math.round(row.negative_share * 100)}%
                          </span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
