/**
 * The public review page - what a customer sees. No login.
 *
 * Deliberately does NOT show the customer the sentiment verdict. Telling
 * someone "we classified your complaint as negative, 91% confident" is
 * unsettling and invites arguing with the model. They get a thank-you; the
 * analysis goes to the manager.
 */

import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Button, ErrorNote, Field, inputClass } from '../components/ui'

export default function SubmitReview() {
  const [restaurants, setRestaurants] = useState([])
  const [branches, setBranches] = useState([])
  const [restaurantId, setRestaurantId] = useState('')
  const [branchId, setBranchId] = useState('')
  const [text, setText] = useState('')
  const [stars, setStars] = useState(0)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  // The restaurant list needs a login, so an anonymous visitor may get nothing
  // back. That is fine - they can still submit if an id is already selected.
  useEffect(() => {
    api.listRestaurants()
      .then((list) => {
        setRestaurants(list)
        if (list.length) setRestaurantId(String(list[0].restaurant_id))
      })
      .catch(() => setRestaurants([]))
  }, [])

  useEffect(() => {
    if (!restaurantId) return
    api.listBranches(restaurantId).then(setBranches).catch(() => setBranches([]))
  }, [restaurantId])

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.submitReview({
        restaurant_id: Number(restaurantId),
        branch_id: branchId ? Number(branchId) : null,
        review_text: text.trim(),
        star_rating: stars || null,
        source: 'web',
      })
      setDone(true)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="mx-auto max-w-md py-16 text-center">
        <div
          className="mx-auto grid h-16 w-16 place-items-center rounded-full text-2xl"
          style={{ background: 'var(--herb)', color: '#fffdf8' }}
          aria-hidden="true"
        >
          ✓
        </div>
        <h1 className="display mt-5 text-2xl font-semibold">Thank you</h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Your feedback has been sent to the restaurant team.
        </p>
        <Button
          variant="ghost"
          className="mt-6"
          onClick={() => {
            setDone(false)
            setText('')
            setStars(0)
          }}
        >
          Leave another review
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-lg">
      <div className="text-center">
        <p className="text-xs uppercase tracking-[0.18em]" style={{ color: 'var(--text-muted)' }}>
          We would love to hear from you
        </p>
        <h1 className="display mt-2 text-3xl font-semibold">Tell us how it went</h1>
        <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Your feedback goes straight to the team who served you.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="card mt-7 space-y-5 p-7">
        {restaurants.length > 0 && (
          <Field label="Restaurant">
            <select value={restaurantId} onChange={(e) => setRestaurantId(e.target.value)}
                    className={inputClass}>
              {restaurants.map((r) => (
                <option key={r.restaurant_id} value={r.restaurant_id}>{r.name}</option>
              ))}
            </select>
          </Field>
        )}

        {branches.length > 0 && (
          <Field label="Branch" hint="Optional, but it helps us route your feedback.">
            <select value={branchId} onChange={(e) => setBranchId(e.target.value)}
                    className={inputClass}>
              <option value="">Not sure</option>
              {branches.map((b) => (
                <option key={b.branch_id} value={b.branch_id}>
                  {b.branch_name}{b.city ? ` — ${b.city}` : ''}
                </option>
              ))}
            </select>
          </Field>
        )}

        <Field label="Rating" hint="Optional.">
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setStars(stars === value ? 0 : value)}
                aria-label={`${value} star${value > 1 ? 's' : ''}`}
                aria-pressed={stars >= value}
                className="text-3xl leading-none transition hover:scale-110"
                style={{ color: stars >= value ? 'var(--brass)' : 'var(--gridline)' }}
              >
                ★
              </button>
            ))}
          </div>
        </Field>

        <Field label="Your review">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            required
            minLength={5}
            placeholder="What went well? What could be better?"
            className="w-full resize-y rounded-xl border px-3.5 py-3 text-sm leading-relaxed
                       outline-none hairline transition focus:border-[#1f4d3f]
                       focus:ring-2 focus:ring-[#1f4d3f]/15"
            style={{ background: 'rgba(255,255,255,0.7)' }}
          />
        </Field>

        <ErrorNote error={error} />

        <Button type="submit" disabled={busy || text.trim().length < 5 || !restaurantId}
                className="w-full">
          {busy ? 'Sending...' : 'Send feedback'}
        </Button>
      </form>
    </div>
  )
}
