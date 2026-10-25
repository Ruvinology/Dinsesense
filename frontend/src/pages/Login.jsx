import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Button, ErrorNote, Field, inputClass } from '../components/ui'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('manager@dinesense.ai')
  const [password, setPassword] = useState('dinesense123')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

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
    <div className="grid min-h-screen place-items-center px-6 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span
            className="mx-auto grid h-14 w-14 place-items-center rounded-full text-base font-bold"
            style={{ background: 'var(--herb)', color: '#fffdf8' }}
            aria-hidden="true"
          >
            DS
          </span>
          <h1 className="display mt-4 text-2xl font-semibold">DineSense</h1>
          <p className="mt-1 text-xs uppercase tracking-[0.18em]"
             style={{ color: 'var(--text-muted)' }}>
            Guest Intelligence
          </p>
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

        <p className="mt-5 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
          Demo accounts are pre-filled · admin@dinesense.ai for the admin view
        </p>
      </div>
    </div>
  )
}
