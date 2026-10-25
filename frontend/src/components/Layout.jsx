import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

function Nav({ to, children }) {
  return (
    <NavLink
      to={to}
      end
      className="relative px-1 py-3 text-sm font-medium transition"
      style={({ isActive }) => ({
        color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
      })}
    >
      {({ isActive }) => (
        <>
          {children}
          <span
            className="absolute inset-x-0 -bottom-px h-[2px] rounded-full transition-opacity"
            style={{ background: 'var(--brass)', opacity: isActive ? 1 : 0 }}
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
        className="sticky top-0 z-20 border-b hairline backdrop-blur"
        style={{ background: 'rgba(255, 253, 248, 0.92)' }}
      >
        <div className="mx-auto flex max-w-7xl items-center gap-8 px-6">
          <NavLink to="/" className="flex items-center gap-2.5 py-3">
            <span
              className="grid h-9 w-9 place-items-center rounded-full text-xs font-bold"
              style={{ background: 'var(--herb)', color: '#fffdf8' }}
              aria-hidden="true"
            >
              DS
            </span>
            <span className="leading-tight">
              <span className="display block text-[15px] font-semibold">DineSense</span>
              <span className="block text-[10px] uppercase tracking-[0.16em]"
                    style={{ color: 'var(--text-muted)' }}>
                Guest Intelligence
              </span>
            </span>
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
                         hairline hover:bg-black/[0.03]"
              style={{ color: 'var(--text-secondary)' }}
            >
              Guest feedback page
            </NavLink>

            {user && (
              <div className="flex items-center gap-3 border-l pl-4 hairline">
                <span
                  className="grid h-8 w-8 place-items-center rounded-full text-xs font-semibold"
                  style={{ background: 'var(--surface-2)', color: 'var(--text-secondary)' }}
                  aria-hidden="true"
                >
                  {user.name.split(' ').map((p) => p[0]).slice(0, 2).join('')}
                </span>
                <div className="leading-tight">
                  <p className="text-xs font-medium">{user.name}</p>
                  <button
                    onClick={() => { logout(); navigate('/login') }}
                    className="text-[11px] underline"
                    style={{ color: 'var(--text-muted)' }}
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
          DineSense AI · sentiment, aspects and urgency from guest feedback
        </p>
      </footer>
    </div>
  )
}
