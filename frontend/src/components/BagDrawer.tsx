import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import { maxFor } from './ShopContext'
import { useChat } from './useChat'
import { useShop } from './useShop'
import BulldogAvatar from './BulldogAvatar'

// Slide-in shopping bag (Problem 9, improvement 1).
export default function BagDrawer() {
  const { bag, units, subtotal, bagOpen, closeBag, setQuantity, removeFromBag, lastAdded } = useShop()
  const { openChat } = useChat()

  useEffect(() => {
    if (!bagOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && closeBag()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [bagOpen, closeBag])

  return (
    <>
      <div className={`bag-overlay${bagOpen ? ' open' : ''}`} onClick={closeBag} aria-hidden="true" />
      <aside className={`bag-drawer${bagOpen ? ' open' : ''}`} aria-label="Shopping bag" aria-hidden={!bagOpen}>
        <header className="bag-header">
          <div>
            <h2>Your bag</h2>
            <span className="bag-count">
              {units} {units === 1 ? 'item' : 'items'}
            </span>
          </div>
          <button className="bag-close" onClick={closeBag} aria-label="Close bag">
            ×
          </button>
        </header>

        {lastAdded && <p className="bag-added">✓ {lastAdded}</p>}

        {bag.length === 0 ? (
          <div className="bag-empty">
            <BulldogAvatar size={96} mood="sleepy" />
            <p>
              <strong>Handsome Dan is guarding an empty bag.</strong>
              <br />
              Wake him up with something good.
            </p>
            <Link to="/products" className="btn btn-primary" onClick={closeBag}>
              Browse products
            </Link>
          </div>
        ) : (
          <ul className="bag-lines">
            {bag.map(({ product: p, size, quantity }) => {
              const max = maxFor(p, size)
              return (
                <li key={`${p.product_id}-${size}`} className="bag-line">
                  <Link to={`/products/${p.product_id}`} onClick={closeBag} className="bag-thumb">
                    <img src={p.image_url} alt={p.name} />
                  </Link>
                  <div className="bag-line-info">
                    <Link to={`/products/${p.product_id}`} onClick={closeBag} className="bag-line-name">
                      {p.name}
                    </Link>
                    <span className="bag-line-meta">
                      Size {size} · {formatPrice(p.price)} each
                      {max <= 5 && max > 0 && <em> · only {p.stock_by_size[size]} in stock</em>}
                    </span>
                    <div className="bag-line-controls">
                      <div className="qty" role="group" aria-label={`Quantity of ${p.name}`}>
                        <button onClick={() => setQuantity(p.product_id, size, quantity - 1)} disabled={quantity <= 1} aria-label="Decrease">
                          −
                        </button>
                        <span>{quantity}</span>
                        <button onClick={() => setQuantity(p.product_id, size, quantity + 1)} disabled={quantity >= max} aria-label="Increase">
                          +
                        </button>
                      </div>
                      <button className="bag-remove" onClick={() => removeFromBag(p.product_id, size)}>
                        Remove
                      </button>
                    </div>
                  </div>
                  <strong className="bag-line-total">{formatPrice(p.price * quantity)}</strong>
                </li>
              )
            })}
          </ul>
        )}

        {bag.length > 0 && (
          <footer className="bag-footer">
            <div className="bag-subtotal">
              <span>Subtotal</span>
              <strong>{formatPrice(subtotal)}</strong>
            </div>
            <p className="bag-note">Quantities are capped at what's in stock. Shipping and taxes are calculated at checkout.</p>
            <button className="btn btn-primary btn-block" disabled title="Online checkout isn't open yet">
              Checkout (coming soon)
            </button>
            <button
              className="btn btn-outline btn-block"
              onClick={() => {
                closeBag()
                openChat('Can you check everything in my bag is in stock?')
              }}
            >
              Ask the assistant about my bag
            </button>
          </footer>
        )}
      </aside>
    </>
  )
}
