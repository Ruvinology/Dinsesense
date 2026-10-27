import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Button, ErrorNote, Field, inputClass } from '../components/ui'

// Shown on the login page on purpose: DineSense is a public demo, and these are
// the accounts backend/seed.py creates. Change the password (and this list)
// before using the app with real restaurant data.
const DEMO_ACCOUNTS = [
  { role: 'Admin', note: 'all restaurants, plus the Admin page',
    email: 'admin@dinesense.ai', password: 'dinesense123' },
  { role: 'Manager', note: "one restaurant's dashboard",
    email: 'manager@dinesense.ai', password: 'dinesense123' },
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState(DEMO_ACCOUNTS[1].email)
  const [password, setPassword] = useState(DEMO_ACCOUNTS[1].password)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  function fillAccount(account) {
    setEmail(account.email)
    setPassword(account.password)
    setError(null)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await login(email, password)
      navigate(location.state?.from || '/', { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center px-6 py-12"
         style={{ background: 'var(--header)' }}>
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span
            className="mx-auto grid h-14 w-14 place-items-center rounded-full text-base font-bold"
            style={{ background: 'var(--header-accent)', color: 'var(--header)' }}
            aria-hidden="true"
          >
            DS
          </span>
          <h1 className="display mt-4 text-2xl font-semibold"
              style={{ color: 'var(--header-ink)' }}>DineSense</h1>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4 p-7">
          <Field label="Email">
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                   className={inputClass} autoComplete="username" required />
          </Field>

          <Field label="Password">
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                   className={inputClass} autoComplete="current-password" required />
          </Field>

          <ErrorNote error={error} />

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <section aria-labelledby="demo-heading" className="mt-5 rounded-2xl p-5"
                 style={{ border: '1px solid var(--header-line)' }}>
          <h2 id="demo-heading" className="text-xs font-semibold uppercase tracking-[0.14em]"
              style={{ color: 'var(--header-accent)' }}>
            Demo accounts
          </h2>
          <p className="mt-1 text-xs" style={{ color: 'var(--header-muted)' }}>
            This is a demo app. Sign in with either account to try it yourself.
          </p>

          <ul className="mt-4 space-y-4">
            {DEMO_ACCOUNTS.map((account) => (
              <li key={account.email} className="flex items-start justify-between gap-3">
                <div className="min-w-0 text-xs leading-relaxed" style={{ color: 'var(--header-ink)' }}>
                  <p>
                    <span className="font-semibold">{account.role}</span>
                    <span style={{ color: 'var(--header-muted)' }}> · {account.note}</span>
                  </p>
                  <p>
                    <span style={{ color: 'var(--header-muted)' }}>Email </span>
                    <span className="font-mono break-all select-all">{account.email}</span>
                  </p>
                  <p>
                    <span style={{ color: 'var(--header-muted)' }}>Password </span>
                    <span className="font-mono select-all">{account.password}</span>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => fillAccount(account)}
                  aria-label={`Fill in the ${account.role.toLowerCase()} account`}
                  className="mt-0.5 shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold transition hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                  style={{ background: 'var(--header-accent)', color: 'var(--header)', outlineColor: 'var(--header-accent)' }}
                >
                  Use
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
