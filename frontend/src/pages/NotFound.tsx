import { Link } from 'react-router-dom'
import BulldogAvatar from '../components/BulldogAvatar'

export default function NotFound() {
  return (
    <section className="section container narrow not-found">
      <BulldogAvatar size={140} mood="sad" />
      <h1>Page not found</h1>
      <p>Handsome Dan sniffed every aisle, but this page wandered off.</p>
      <Link to="/" className="btn btn-gold">
        Head back home
      </Link>
    </section>
  )
}
