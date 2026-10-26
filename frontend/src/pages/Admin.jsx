import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import {
  Button, Card, EmptyNote, ErrorNote, Field, Spinner, inputClass,
} from '../components/ui'

export default function Admin() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [formError, setFormError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [restaurants, users, metrics] = await Promise.all([
        api.listRestaurants(),
        api.listUsers(),
        api.modelMetrics(),
      ])
      const branches = {}
      for (const restaurant of restaurants) {
        branches[restaurant.restaurant_id] = await api.listBranches(restaurant.restaurant_id)
      }
      setData({ restaurants, users, metrics, branches })
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function submit(action) {
    setFormError(null)
    try {
      await action()
      load()
    } catch (err) {
      setFormError(err)
    }
  }

  if (loading && !data) return <Spinner label="Loading admin" />
  if (error) return <ErrorNote error={error} onRetry={load} />
  if (!data) return null

  const comparison = data.metrics.comparison

  return (
    <div className="space-y-6">
      <div>
        <h1 className="display text-3xl font-semibold">Administration</h1>
        <p className="mt-0.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
          Restaurants, branches, users and model status.
        </p>
      </div>

      <ErrorNote error={formError} />

      <Card title="Model status" subtitle="Which model is serving predictions, and how it scored">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Active model</p>
            <p className="mt-0.5 font-mono text-sm">{data.metrics.active_model}</p>
          </div>
          <div>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Version</p>
            <p className="mt-0.5 font-mono text-sm">{data.metrics.model_version}</p>
          </div>
        </div>

        {comparison && (
          <>
            <table className="mt-5 w-full text-sm">
              <thead>
                <tr className="border-b text-xs hairline" style={{ color: 'var(--text-muted)' }}>
                  <th className="pb-2 text-left font-medium">Model</th>
                  <th className="pb-2 text-right font-medium">Accuracy</th>
                  <th className="pb-2 text-right font-medium">Macro F1</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(comparison).map(([name, scores]) => (
                  <tr key={name} className="border-b last:border-0 hairline">
                    <td className="py-2 font-mono text-xs">
                      {name}
                      {name === data.metrics.active_model && (
                        <span className="ml-2 font-sans text-[10px] uppercase tracking-wide"
                              style={{ color: 'var(--text-muted)' }}>
                          serving
                        </span>
                      )}
                    </td>
                    <td className="tabular py-2 text-right">{scores.accuracy?.toFixed(4)}</td>
                    <td className="tabular py-2 text-right font-medium">
                      {scores.macro_f1?.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
              The baseline is not a placeholder — it is the honest comparison the
              deep model has to beat.
            </p>
          </>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Restaurants">
          <ul className="mb-4 space-y-3">
            {data.restaurants.map((restaurant) => (
              <li key={restaurant.restaurant_id} className="rounded-xl border p-4 hairline">
                <p className="text-sm font-medium">{restaurant.name}</p>
                {restaurant.description && (
                  <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                    {restaurant.description}
                  </p>
                )}
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {(data.branches[restaurant.restaurant_id] || []).map((branch) => (
                    <li key={branch.branch_id}
                        className="rounded-full px-2.5 py-1 text-xs"
                        style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}>
                      {branch.branch_name}
                    </li>
                  ))}
                </ul>

                <form
                  className="mt-3 flex gap-2"
                  onSubmit={(e) => {
                    e.preventDefault()
                    const form = new FormData(e.target)
                    const name = form.get('branch_name')?.toString().trim()
                    if (!name) return
                    e.target.reset()
                    submit(() =>
                      api.createBranch(restaurant.restaurant_id, {
                        branch_name: name,
                        city: form.get('city')?.toString() || null,
                      }),
                    )
                  }}
                >
                  <input name="branch_name" placeholder="New branch name"
                         className={`${inputClass} text-xs`} />
                  <input name="city" placeholder="City" className={`${inputClass} w-28 text-xs`} />
                  <Button variant="ghost" type="submit" className="shrink-0 text-xs">Add</Button>
                </form>
              </li>
            ))}
          </ul>

          <form
            className="space-y-3 border-t pt-4 hairline"
            onSubmit={(e) => {
              e.preventDefault()
              const form = new FormData(e.target)
              const name = form.get('name')?.toString().trim()
              if (!name) return
              e.target.reset()
              submit(() =>
                api.createRestaurant({
                  name,
                  description: form.get('description')?.toString() || null,
                }),
              )
            }}
          >
            <Field label="Add a restaurant">
              <input name="name" placeholder="Restaurant name" className={inputClass} />
            </Field>
            <input name="description" placeholder="Description (optional)" className={inputClass} />
            <Button type="submit">Create restaurant</Button>
          </form>
        </Card>

        <Card title="Users">
          {data.users.length === 0 ? (
            <EmptyNote>No users yet.</EmptyNote>
          ) : (
            <table className="mb-4 w-full text-sm">
              <thead>
                <tr className="border-b text-xs hairline" style={{ color: 'var(--text-muted)' }}>
                  <th className="pb-2 text-left font-medium">Name</th>
                  <th className="pb-2 text-left font-medium">Email</th>
                  <th className="pb-2 text-left font-medium">Role</th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((user) => (
                  <tr key={user.user_id} className="border-b last:border-0 hairline">
                    <td className="py-2">{user.name}</td>
                    <td className="py-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {user.email}
                    </td>
                    <td className="py-2 text-xs">{user.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <form
            className="space-y-3 border-t pt-4 hairline"
            onSubmit={(e) => {
              e.preventDefault()
              const form = new FormData(e.target)
              e.target.reset()
              submit(() =>
                api.createUser({
                  name: form.get('name'),
                  email: form.get('email'),
                  password: form.get('password'),
                  role: form.get('role'),
                  restaurant_id: form.get('restaurant_id')
                    ? Number(form.get('restaurant_id'))
                    : null,
                }),
              )
            }}
          >
            <Field label="Add a user">
              <input name="name" placeholder="Full name" required className={inputClass} />
            </Field>
            <input name="email" type="email" placeholder="Email" required className={inputClass} />
            <input name="password" type="password" placeholder="Password (min 8 characters)"
                   minLength={8} required className={inputClass} />
            <div className="grid grid-cols-2 gap-3">
              <select name="role" className={inputClass} defaultValue="manager">
                <option value="manager">Manager</option>
                <option value="admin">Admin</option>
              </select>
              <select name="restaurant_id" className={inputClass} defaultValue="">
                <option value="">No restaurant</option>
                {data.restaurants.map((r) => (
                  <option key={r.restaurant_id} value={r.restaurant_id}>{r.name}</option>
                ))}
              </select>
            </div>
            <Button type="submit">Create user</Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
