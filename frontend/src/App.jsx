import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import Admin from './pages/Admin'
import Analyse from './pages/Analyse'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Reviews from './pages/Reviews'
import SubmitReview from './pages/SubmitReview'

/** Blocks a route until we know who the user is. */
function RequireAuth({ children, adminOnly = false }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <Spinner label="Checking your session" />
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (adminOnly && user.role !== 'admin') return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route element={<Layout />}>
            {/* Public - a customer leaving feedback is not logged in */}
            <Route path="/submit" element={<SubmitReview />} />
            <Route path="/analyse" element={<Analyse />} />

            <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
            <Route path="/reviews" element={<RequireAuth><Reviews /></RequireAuth>} />
            <Route path="/admin" element={<RequireAuth adminOnly><Admin /></RequireAuth>} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
