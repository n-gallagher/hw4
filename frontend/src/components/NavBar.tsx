import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from './useAuth'
import { useChat } from './useChat'
import { useShop } from './useShop'
import { SIZES, type Size } from '../api'
import { PawPrint } from './BulldogAvatar'

const mainLinks = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'nav-link active' : 'nav-link'

export default function NavBar() {
  const { user, loading, signOut } = useAuth()
  const { clearResults, closeChat } = useChat()
  const { units, openBag, mySize, setMySize, pawBurst } = useShop()
  const navigate = useNavigate()

  async function handleLogout() {
    navigate('/') // leave protected pages first so they don't redirect to /login
    clearResults() // the next person on this browser shouldn't see this shopper's chat results
    closeChat()
    await signOut()
  }

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="brand">
          <span className="brand-mark">CC</span>
          <span className="brand-text">Campus Customs</span>
        </Link>

        <nav className="nav-main" aria-label="Main">
          {mainLinks.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={linkClass}>
              {l.label}
            </NavLink>
          ))}
        </nav>

        <label className={mySize ? 'size-chip active' : 'size-chip'} title="Shop my size: show stock for your size everywhere">
          <span>My size</span>
          <select
            value={mySize ?? ''}
            onChange={(e) => setMySize((e.target.value || null) as Size | null)}
            aria-label="My size"
          >
            <option value="">Any</option>
            {SIZES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <button className="bag-button" onClick={openBag} aria-label={`Open bag, ${units} items`}>
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path
              fill="currentColor"
              d="M7 7V6a5 5 0 0 1 10 0v1h3l-1 14H5L4 7h3Zm2 0h6V6a3 3 0 0 0-6 0v1Zm-2.9 2 .8 10h10.2l.8-10H6.1Z"
            />
          </svg>
          {units > 0 && <span className="bag-badge">{units}</span>}
          {pawBurst > 0 && (
            // Handsome Dan stamps the bag: paw prints pop out of the icon on every add
            <span className="paw-burst" key={pawBurst} aria-hidden="true">
              <PawPrint size={13} />
              <PawPrint size={11} />
              <PawPrint size={12} />
            </span>
          )}
        </button>

        <nav className="nav-account" aria-label="Account">
          {loading ? null : user ? (
            <>
              <NavLink to="/account" className={linkClass}>
                Hi, {user.first_name}
              </NavLink>
              <button className="nav-cta" onClick={handleLogout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className={linkClass}>
                Log in
              </NavLink>
              <NavLink to="/create-account" className="nav-cta">
                Create account
              </NavLink>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
