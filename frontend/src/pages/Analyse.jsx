import { useState } from 'react'
import { api } from '../api/client'
import {
  Button, Card, ErrorNote, SentimentBadge, UrgencyBadge, prettyAspect,
} from '../components/ui'

const EXAMPLES = [
  'The food was excellent, but the service was extremely slow.',
  'Found a piece of glass in my pasta and the manager just shrugged.',
  'Cozy little place, fair prices, and the staff were lovely.',
  'They charged me twice for the same meal and nobody would help.',
]

export default function Analyse() {
  const [text, setText] = useState(EXAMPLES[0])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function run(value) {
    const input = (value ?? text).trim()
    if (input.length < 5) return
    setBusy(true)
    setError(null)
    try {
      setResult(await api.analyse(input))
    } catch (err) {
      setError(err)
      setResult(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="display text-3xl font-semibold">Analyse a review</h1>
        <p className="mt-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Run one review through the model without storing it.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Review text">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            className="w-full resize-y rounded-xl border px-3.5 py-3 text-sm leading-relaxed
                       outline-none hairline transition focus:border-[#1d6142]
                       focus:ring-2 focus:ring-[#1d6142]/15"
            style={{ background: 'rgba(255,255,255,0.7)' }}
            placeholder="Paste or type a customer review..."
          />

          <div className="mt-3 flex items-center gap-3">
            <Button onClick={() => run()} disabled={busy || text.trim().length < 5}>
              {busy ? 'Analysing...' : 'Analyse'}
            </Button>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {text.trim().length} characters
            </span>
          </div>

          <div className="mt-5">
            <p className="mb-2 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
              Try an example
            </p>
            <div className="space-y-1.5">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  onClick={() => {
                    setText(example)
                    run(example)
                  }}
                  className="block w-full rounded-xl border px-3.5 py-2.5 text-left text-xs
                             transition hairline hover:bg-black/[0.03] hover:shadow-sm"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        </Card>

        <Card title="Result">
          <ErrorNote error={error} />

          {!result && !error && (
            <p className="py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              Analyse a review to see the breakdown.
            </p>
          )}

          {result && (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                <SentimentBadge value={result.sentiment} />
                <UrgencyBadge value={result.urgency} />
                <span className="tabular ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>
                  {Math.round(result.confidence * 100)}% confident
                </span>
              </div>

              {/* A confidence number means little without a sense of scale, so show it. */}
              <div>
                <div className="h-1.5 w-full overflow-hidden rounded-full"
                     style={{ background: 'var(--gridline)' }}>
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.round(result.confidence * 100)}%`,
                      background: result.sentiment === 'negative' ? 'var(--negative)'
                        : result.sentiment === 'positive' ? 'var(--positive)' : 'var(--neutral)',
                    }}
                  />
                </div>
                <p className="mt-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                  Model: {result.model_version}
                  {result.urgency_reason && ` · flagged: ${result.urgency_reason}`}
                </p>
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide"
                    style={{ color: 'var(--text-muted)' }}>
                  Aspects detected
                </h3>
                {result.aspects.length === 0 ? (
                  <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                    No specific aspect matched.
                  </p>
                ) : (
                  <ul className="space-y-1.5">
                    {result.aspects.map((aspect) => (
                      <li key={aspect.aspect}
                          className="flex items-center gap-3 rounded-xl border px-3.5 py-2.5 hairline">
                        <span className="text-sm">{prettyAspect(aspect.aspect)}</span>
                        <span className="ml-auto">
                          <SentimentBadge value={aspect.sentiment} />
                        </span>
                        <span className="tabular w-10 text-right text-xs"
                              style={{ color: 'var(--text-muted)' }}>
                          {Math.round(aspect.confidence * 100)}%
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide"
                    style={{ color: 'var(--text-muted)' }}>
                  Recommended action
                </h3>
                <ul className="space-y-1.5">
                  {result.recommendations.map((rec) => (
                    <li key={rec} className="flex gap-2 text-sm">
                      <span aria-hidden="true" style={{ color: 'var(--text-muted)' }}>→</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
