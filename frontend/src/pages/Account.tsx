import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../components/useAuth'
import { useChat } from '../components/useChat'

export default function Account() {
  const { user, loading } = useAuth()
  const { openChat } = useChat()

  if (loading) {
    return (
      <section className="section container">
        <p className="muted">Loading…</p>
      </section>
    )
  }
  if (!user) return <Navigate to="/login" replace />

  return (
    <section className="section container narrow">
      <p className="eyebrow eyebrow-dark">My account</p>
      <h1>Welcome, {user.first_name}!</h1>
      <p className="muted">You’re logged in to Campus Customs.</p>

      <dl className="account-details">
        <dt>Name</dt>
        <dd>
          {user.first_name} {user.last_name}
        </dd>
        <dt>Email</dt>
        <dd>{user.email}</dd>
        <dt>Customer #</dt>
        <dd>{user.id}</dd>
      </dl>

      <div className="hero-actions">
        <Link to="/products" className="btn btn-primary">
          Browse products
        </Link>
        <button className="btn btn-outline" onClick={() => openChat()}>
          Chat with the shop
        </button>
      </div>
    </section>
  )
}
