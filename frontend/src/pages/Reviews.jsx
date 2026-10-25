import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  Button, Card, EmptyNote, ErrorNote, Field, SentimentBadge, Spinner,
  UrgencyBadge, inputClass, prettyAspect,
} from '../components/ui'

export default function Reviews() {
  const [params, setParams] = useSearchParams()
  const [reviews, setReviews] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [upload, setUpload] = useState(null)
  const fileRef = useRef(null)

  const sentiment = params.get('sentiment') || ''
  const urgency = params.get('urgency') || ''
  const search = params.get('search') || ''

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setReviews(await api.listReviews({ sentiment, urgency, search, limit: 100 }))
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [sentiment, urgency, search])

  useEffect(() => {
    load()
  }, [load])

  function setFilter(key, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setUpload({ busy: true })
    try {
      const restaurants = await api.listRestaurants()
      if (!restaurants.length) throw new Error('No restaurant found to attach these reviews to.')
      const result = await api.uploadCsv(restaurants[0].restaurant_id, file)
      setUpload({ busy: false, result })
      load()
    } catch (err) {
      setUpload({ busy: false, error: err })
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="display text-3xl font-semibold">Guest reviews</h1>
          <p className="mt-0.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
            {loading ? 'Loading...' : `${reviews.length} shown`}
          </p>
        </div>
        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            onChange={handleUpload}
            className="hidden"
            id="csv-upload"
          />
          <Button variant="ghost" onClick={() => fileRef.current?.click()}
                  disabled={upload?.busy}>
            {upload?.busy ? 'Uploading...' : 'Upload CSV'}
          </Button>
        </div>
      </div>

      {upload?.result && (
        <div className="rounded-lg px-4 py-3 text-sm"
             style={{ background: 'var(--positive-soft)', color: '#1c5cab' }}>
          <p className="font-medium">
            Stored {upload.result.stored} of {upload.result.received} rows
          </p>
          {upload.result.errors?.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-xs">
              {upload.result.errors.slice(0, 5).map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      <ErrorNote error={upload?.error} />

      <Card>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Search text">
            <input
              defaultValue={search}
              onBlur={(e) => setFilter('search', e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && setFilter('search', e.target.value)}
              placeholder="e.g. delivery"
              className={inputClass}
            />
          </Field>
          <Field label="Sentiment">
            <select value={sentiment} onChange={(e) => setFilter('sentiment', e.target.value)}
                    className={inputClass}>
              <option value="">All</option>
              <option value="positive">Positive</option>
              <option value="neutral">Neutral</option>
              <option value="negative">Negative</option>
            </select>
          </Field>
          <Field label="Urgency">
            <select value={urgency} onChange={(e) => setFilter('urgency', e.target.value)}
                    className={inputClass}>
              <option value="">All</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </Field>
        </div>
      </Card>

      <ErrorNote error={error} onRetry={load} />

      {loading ? (
        <Spinner label="Loading reviews" />
      ) : reviews.length === 0 ? (
        <Card>
          <EmptyNote>No reviews match these filters.</EmptyNote>
        </Card>
      ) : (
        <div className="space-y-3">
          {reviews.map((review) => (
            <article key={review.review_id} className="card card-hover p-6">
              <div className="flex flex-wrap items-center gap-2">
                {review.prediction && <SentimentBadge value={review.prediction.sentiment} />}
                {review.prediction?.urgency !== 'low' && (
                  <UrgencyBadge value={review.prediction.urgency} />
                )}
                <span className="tabular ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>
                  {review.star_rating ? `${review.star_rating}★ · ` : ''}
                  {review.review_date} · {review.source}
                </span>
              </div>

              <p className="mt-3 text-sm">{review.review_text}</p>

              {review.aspects.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-1.5">
                  {review.aspects.map((aspect) => (
                    <li
                      key={aspect.aspect}
                      className="rounded-full px-2.5 py-1 text-xs"
                      style={{
                        background: 'var(--surface-2)',
                        color: 'var(--text-secondary)',
                        borderLeft: `2px solid ${
                          aspect.aspect_sentiment === 'negative' ? 'var(--negative)'
                            : aspect.aspect_sentiment === 'positive' ? 'var(--positive)'
                            : 'var(--neutral)'
                        }`,
                      }}
                    >
                      {prettyAspect(aspect.aspect)}
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
