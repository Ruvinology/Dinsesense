import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

function Nav({ to, children }) {
  return (
    <NavLink
      to={to}
      end
      className="relative px-1 py-3 text-sm font-medium transition"
      style={({ isActive }) => ({
        color: isActive ? 'var(--header-ink)' : 'var(--header-muted)',
      })}
    >
      {({ isActive }) => (
        <>
          {children}
          <span
            className="absolute inset-x-0 -bottom-px h-[2px] rounded-full transition-opacity"
            style={{ background: 'var(--header-accent)', opacity: isActive ? 1 : 0 }}
            aria-hidden="true"
          />
        </>
      )}
    </NavLink>
  )
}

export default function Layout() {
  const { user, logout, isAdmin } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="min-h-full">
      <header
        className="sticky top-0 z-20 border-b"
        style={{ background: 'var(--header)', borderColor: 'var(--header-line)' }}
      >
        <div className="mx-auto flex max-w-7xl items-center gap-8 px-6">
          <NavLink to="/" className="flex items-center gap-2.5 py-3">
            <span
              className="grid h-9 w-9 place-items-center rounded-full text-xs font-bold"
              style={{ background: 'var(--header-accent)', color: 'var(--header)' }}
              aria-hidden="true"
            >
              DS
            </span>
            <span className="display text-[17px] font-semibold leading-tight"
                  style={{ color: 'var(--header-ink)' }}>DineSense</span>
          </NavLink>

          <nav className="flex items-center gap-6">
            <Nav to="/">Dashboard</Nav>
            <Nav to="/reviews">Reviews</Nav>
            <Nav to="/analyse">Analyse</Nav>
            {isAdmin && <Nav to="/admin">Admin</Nav>}
          </nav>

          <div className="ml-auto flex items-center gap-4">
            <NavLink
              to="/submit"
              className="rounded-full border px-3.5 py-1.5 text-xs font-medium transition
                         hover:bg-white/10"
              style={{ color: 'var(--header-ink)', borderColor: 'var(--header-line)' }}
            >
              Guest feedback page
            </NavLink>

            {user && (
              <div className="flex items-center gap-3 border-l pl-4"
                   style={{ borderColor: 'var(--header-line)' }}>
                <span
                  className="grid h-8 w-8 place-items-center rounded-full text-xs font-semibold"
                  style={{ background: 'var(--header-line)', color: 'var(--header-ink)' }}
                  aria-hidden="true"
                >
                  {user.name.split(' ').map((p) => p[0]).slice(0, 2).join('')}
                </span>
                <div className="leading-tight">
                  <p className="text-xs font-medium" style={{ color: 'var(--header-ink)' }}>{user.name}</p>
                  <button
                    onClick={() => { logout(); navigate('/login') }}
                    className="text-[11px] underline"
                    style={{ color: 'var(--header-muted)' }}
                  >
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        <Outlet />
      </main>

      <footer className="mx-auto max-w-7xl px-6 pb-8 pt-2">
        <p className="text-center text-[11px]" style={{ color: 'var(--text-muted)' }}>
          Developed and designed by Ruim Palihawadana
        </p>
      </footer>
    </div>
  )
}
