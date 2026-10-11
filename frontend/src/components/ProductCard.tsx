import type { CSSProperties, MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice, SIZES, type ProductSummary, type Size } from '../api'
import { useShop } from './useShop'

// One product card (image, name, price, short description, size availability).
// Used by the Products page and by the chat results the agent puts on the page.
// Hover: the photo zooms and a quick-add size row slides up (adds 1 to the bag without leaving the grid).
export default function ProductCard({ product: p, style }: { product: ProductSummary; style?: CSSProperties }) {
  const { mySize, addToBag } = useShop()
  const inMySize = mySize ? (p.stock_by_size[mySize] ?? 0) : null
  const soldOutInMySize = inMySize === 0

  function quickAdd(e: MouseEvent, size: Size) {
    e.preventDefault() // the card is a link; quick-add shouldn't navigate
    e.stopPropagation()
    addToBag(p, size, 1)
  }

  return (
    <Link to={`/products/${p.product_id}`} className={soldOutInMySize ? 'product-card faded' : 'product-card'} style={style}>
      <div className="product-img">
        <img src={p.image_url} alt={p.name} loading="lazy" />
        <span className="tag">{p.category}</span>
        {mySize && (
          <span className={`size-badge ${soldOutInMySize ? 'out' : inMySize! <= 5 ? 'low' : 'ok'}`}>
            {mySize} · {soldOutInMySize ? 'sold out' : inMySize! <= 5 ? `only ${inMySize} left` : `${inMySize} left`}
          </span>
        )}
        <div className="quick-add" aria-label={`Quick add ${p.name}`}>
          <span className="quick-add-label">Quick add</span>
          <div className="quick-add-sizes">
            {SIZES.map((s) => {
              const n = p.stock_by_size[s] ?? 0
              return (
                <button
                  key={s}
                  className={`${n === 0 ? 'out' : ''} ${mySize === s ? 'mine' : ''}`}
                  disabled={n === 0}
                  onClick={(e) => quickAdd(e, s)}
                  title={n === 0 ? `${s}: sold out` : `Add ${s} to bag (${n} in stock)`}
                >
                  {s}
                </button>
              )
            })}
          </div>
        </div>
      </div>
      <div className="product-body">
        <div className="product-title-row">
          <h3>{p.name}</h3>
          <span className="price">{formatPrice(p.price)}</span>
        </div>
        <p className="product-desc">{p.short_description}</p>
        <div className="availability">
          <div className="avail-bar">
            {Array.from({ length: p.sizes_total }, (_, i) => (
              <span key={i} className={i < p.sizes_in_stock ? 'on' : ''} />
            ))}
          </div>
          <span>
            {p.sizes_in_stock}/{p.sizes_total} sizes in stock
          </span>
        </div>
      </div>
    </Link>
  )
}
