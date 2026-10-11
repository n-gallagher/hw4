import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { signup } from '../api'
import { useAuth } from '../components/useAuth'

const MIN_PASSWORD = 8

function passwordStrength(pw: string): { score: number; label: string } {
  if (!pw) return { score: 0, label: '' }
  let score = 0
  if (pw.length >= MIN_PASSWORD) score++
  if (pw.length >= 12) score++
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++
  if (/\d/.test(pw)) score++
  if (/[^A-Za-z0-9]/.test(pw)) score++
  const labels = ['Too short', 'Weak', 'Fair', 'Good', 'Strong', 'Very strong']
  return { score: pw.length < MIN_PASSWORD ? 0 : score, label: pw.length < MIN_PASSWORD ? labels[0] : labels[score] }
}

export default function CreateAccount() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user && !submitting) return <Navigate to="/account" replace />

  const update = (field: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [field]: e.target.value })

  const strength = passwordStrength(form.password)
  const mismatch = form.confirm.length > 0 && form.confirm !== form.password

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (form.password.length < MIN_PASSWORD) return setError(`Password must be at least ${MIN_PASSWORD} characters.`)
    if (form.password !== form.confirm) return setError('Passwords do not match.')

    setSubmitting(true)
    try {
      const newUser = await signup({
        first_name: form.firstName,
        last_name: form.lastName,
        email: form.email,
        password: form.password,
        confirm_password: form.confirm,
      })
      setUser(newUser)
      navigate('/account', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create account.')
      setSubmitting(false)
    }
  }

  return (
    <section className="section container auth">
      <form className="auth-card" onSubmit={handleSubmit} noValidate>
        <h1>Create account</h1>
        <p className="muted">Join Campus Customs so Handsome Dan remembers your chats when you come back.</p>

        <div className="form-row">
          <label>
            First name
            <input value={form.firstName} onChange={update('firstName')} autoComplete="given-name" required />
          </label>
          <label>
            Last name
            <input value={form.lastName} onChange={update('lastName')} autoComplete="family-name" required />
          </label>
        </div>
        <label>
          Email
          <input type="email" value={form.email} onChange={update('email')} autoComplete="email" required />
        </label>
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={update('password')}
            autoComplete="new-password"
            required
          />
        </label>
        {form.password && (
          <div className="strength" aria-live="polite">
            <div className="strength-bar">
              {[1, 2, 3, 4, 5].map((i) => (
                <span key={i} className={i <= strength.score ? `on s${strength.score}` : ''} />
              ))}
            </div>
            <span>{strength.label}</span>
          </div>
        )}
        <label>
          Confirm password
          <input
            type="password"
            value={form.confirm}
            onChange={update('confirm')}
            autoComplete="new-password"
            aria-invalid={mismatch}
            required
          />
        </label>
        {mismatch && <p className="field-hint">Passwords don’t match yet.</p>}

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          className="btn btn-primary btn-block"
          disabled={submitting || !form.firstName || !form.lastName || !form.email || !form.password || !form.confirm}
        >
          {submitting ? 'Creating account…' : 'Create account'}
        </button>

        <p className="auth-switch">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </section>
  )
}
