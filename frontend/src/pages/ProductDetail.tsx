import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { formatPrice, getProduct, type ProductDetail as Product, type StockStatus } from '../api'
import { useChat } from '../components/useChat'
import { useShop } from '../components/useShop'
import { maxFor } from '../components/ShopContext'
import type { Size } from '../api'

const statusLabel: Record<StockStatus, string> = {
  in_stock: 'In stock',
  low: 'Low stock',
  sold_out: 'Sold out',
}

export default function ProductDetail() {
  const { productId = '' } = useParams()
  // key resets all page state when navigating between products
  return <ProductView key={productId} productId={productId} />
}

function ProductView({ productId }: { productId: string }) {
  const [product, setProduct] = useState<Product | null>(null)
  const [error, setError] = useState('')
  const { openChat } = useChat()
  const { mySize, addToBag, bag } = useShop()
  const [picked, setPicked] = useState<string | null>(null)
  const [qty, setQty] = useState(1)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    getProduct(productId)
      .then(setProduct)
      .catch((e: Error) =>
        setError(e.message === 'Not found' ? 'We couldn’t find that product.' : 'Could not load this product.'),
      )
  }, [productId])

  if (error) {
    return (
      <section className="section container narrow">
        <p className="error-box">{error}</p>
        <Link to="/products">← Back to all products</Link>
      </section>
    )
  }

  if (!product) {
    return (
      <section className="section container">
        <p className="muted">Loading…</p>
      </section>
    )
  }

  const maxQty = Math.max(...product.sizes.map((s) => s.quantity), 1)
  // "Shop my size": start on the shopper's size if it's in stock
  const selected = picked ?? (mySize && (product.stock_by_size[mySize] ?? 0) > 0 ? mySize : null)
  const setSelected = (size: string) => {
    setPicked(size)
    setQty(1)
    setNotice('')
  }
  const selectedSize = product.sizes.find((s) => s.size === selected)
  const inBag = selected ? (bag.find((i) => i.product.product_id === product.product_id && i.size === selected)?.quantity ?? 0) : 0
  const canAdd = selected ? Math.max(maxFor(product, selected as Size) - inBag, 0) : 0

  function handleAdd() {
    if (!selected) return
    const res = addToBag(product!, selected as Size, qty)
    setNotice(res.ok ? '' : res.message)
    setQty(1)
  }

  return (
    <section className="section container">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/products">Products</Link>
        <span>/</span>
        <span>{product.category}</span>
        <span>/</span>
        <span className="current">{product.name}</span>
      </nav>

      <div className="detail">
        {/* Hover magnifier: the photo zooms 2x and follows the cursor */}
        <div
          className="detail-img magnifier"
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect()
            e.currentTarget.style.setProperty('--zx', `${((e.clientX - r.left) / r.width) * 100}%`)
            e.currentTarget.style.setProperty('--zy', `${((e.clientY - r.top) / r.height) * 100}%`)
          }}
        >
          <img src={product.image_url} alt={product.name} />
          <span className="zoom-hint">Hover to zoom</span>
        </div>

        <div className="detail-info">
          <p className="eyebrow eyebrow-dark">{product.garment_type}</p>
          <h1>{product.name}</h1>
          <p className="detail-price">{formatPrice(product.price)}</p>
          <p className="detail-desc">{product.description}</p>

          {product.colors.length > 0 && (
            <div className="detail-block">
              <h4>Colors</h4>
              <div className="color-list">
                {product.colors.map((c) => (
                  <span key={c} className="color-pill">
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="detail-block">
            <h4>
              Size &amp; stock
              <span className="detail-sub">
                {product.total_stock} units across {product.sizes_in_stock} of {product.sizes_total} sizes
              </span>
            </h4>
            <div className="size-grid">
              {product.sizes.map((s) => (
                <button
                  key={s.size}
                  className={`size-btn ${s.status} ${selected === s.size ? 'selected' : ''}`}
                  disabled={s.status === 'sold_out'}
                  onClick={() => setSelected(s.size)}
                  title={`${s.size}: ${s.quantity} in stock`}
                >
                  {s.size}
                  {mySize === s.size && <span className="your-size-dot" title="Your size" />}
                </button>
              ))}
            </div>
            <p className="size-note">
              {selectedSize
                ? `${selectedSize.size}: ${selectedSize.quantity} in stock (${statusLabel[selectedSize.status].toLowerCase()})`
                : 'Select a size to see its availability.'}
            </p>

            <table className="stock-table">
              <tbody>
                {product.sizes.map((s) => (
                  <tr key={s.size}>
                    <th scope="row">{s.size}</th>
                    <td className="stock-bar-cell">
                      <span
                        className={`stock-bar ${s.status}`}
                        style={{ width: `${(s.quantity / maxQty) * 100}%` }}
                      />
                    </td>
                    <td className="stock-qty">{s.quantity}</td>
                    <td className={`stock-status ${s.status}`}>{statusLabel[s.status]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="buy-box">
            <div className="qty" role="group" aria-label="Quantity">
              <button onClick={() => setQty((q) => Math.max(1, q - 1))} disabled={qty <= 1} aria-label="Decrease">
                −
              </button>
              <span>{qty}</span>
              <button onClick={() => setQty((q) => Math.min(canAdd, q + 1))} disabled={!selected || qty >= canAdd} aria-label="Increase">
                +
              </button>
            </div>
            <button className="btn btn-primary btn-add" onClick={handleAdd} disabled={!selected || canAdd === 0}>
              {!selected
                ? 'Select a size'
                : canAdd === 0
                  ? inBag > 0
                    ? `All ${inBag} in your bag`
                    : 'Sold out'
                  : `Add to bag · ${formatPrice(product.price * qty)}`}
            </button>
          </div>
          {inBag > 0 && <p className="size-note">{inBag} in your bag (size {selected}).</p>}
          {notice && <p className="form-error">{notice}</p>}

          <button className="btn btn-outline" onClick={() => openChat(`Tell me about the ${product.name}`)}>
            Ask the assistant about this item
          </button>
        </div>
      </div>
    </section>
  )
}
