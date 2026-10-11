import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { formatPrice, getProducts, type ProductSummary } from '../api'
import ProductCard from '../components/ProductCard'
import { useShop } from '../components/useShop'

type SortKey = 'name' | 'price-asc' | 'price-desc' | 'stock'

const sorters: Record<SortKey, (a: ProductSummary, b: ProductSummary) => number> = {
  name: (a, b) => a.name.localeCompare(b.name),
  'price-asc': (a, b) => a.price - b.price || a.name.localeCompare(b.name),
  'price-desc': (a, b) => b.price - a.price || a.name.localeCompare(b.name),
  stock: (a, b) => b.total_stock - a.total_stock,
}

function median(values: number[]) {
  if (!values.length) return 0
  const s = [...values].sort((a, b) => a - b)
  const mid = Math.floor(s.length / 2)
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
}

export default function Products() {
  const [products, setProducts] = useState<ProductSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  // Category lives in the URL (?category=Hoodies) so home-page patches and footer links can deep-link here.
  const [params, setParams] = useSearchParams()
  const category = params.get('category') ?? 'All'
  const setCategory = (c: string) => setParams(c === 'All' ? {} : { category: c }, { replace: true })
  const [sort, setSort] = useState<SortKey>('name')
  const { mySize, setMySize } = useShop()
  const [onlyMySize, setOnlyMySize] = useState(false)

  useEffect(() => {
    getProducts()
      .then(setProducts)
      .catch(() => setError('Could not load products. Is the backend running?'))
      .finally(() => setLoading(false))
  }, [])

  const categories = useMemo(() => {
    const counts = new Map<string, number>()
    products.forEach((p) => counts.set(p.category, (counts.get(p.category) ?? 0) + 1))
    return [...counts.entries()].sort((a, b) => b[1] - a[1])
  }, [products])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return products
      .filter((p) => category === 'All' || p.category === category)
      .filter((p) => !(onlyMySize && mySize) || (p.stock_by_size[mySize] ?? 0) > 0)
      .filter(
        (p) =>
          !q ||
          p.name.toLowerCase().includes(q) ||
          p.short_description.toLowerCase().includes(q) ||
          p.garment_type.toLowerCase().includes(q) ||
          p.colors.some((c) => c.toLowerCase().includes(q)),
      )
      .sort(sorters[sort])
  }, [products, query, category, sort, onlyMySize, mySize])

  const stats = useMemo(() => {
    const prices = visible.map((p) => p.price)
    const slots = visible.reduce((n, p) => n + p.sizes_total, 0)
    const inStock = visible.reduce((n, p) => n + p.sizes_in_stock, 0)
    const inSize = mySize ? visible.filter((p) => (p.stock_by_size[mySize] ?? 0) > 0).length : 0
    return {
      inSize,
      count: visible.length,
      min: prices.length ? Math.min(...prices) : 0,
      max: prices.length ? Math.max(...prices) : 0,
      median: median(prices),
      availability: slots ? Math.round((inStock / slots) * 100) : 0,
    }
  }, [visible, mySize])

  return (
    <section className="section container">
      <div className="page-head">
        <div>
          <p className="eyebrow eyebrow-dark">Shop</p>
          <h1>The collection</h1>
          <p className="muted">Officially licensed Yale apparel, with live prices and stock by size.</p>
        </div>
      </div>

      {!loading && !error && (
        <div className="stat-strip" aria-label="Collection summary">
          <div className="stat">
            <span className="stat-value">{stats.count}</span>
            <span className="stat-label">styles shown</span>
          </div>
          <div className="stat">
            <span className="stat-value">
              {formatPrice(stats.min)}–{formatPrice(stats.max)}
            </span>
            <span className="stat-label">price range</span>
          </div>
          <div className="stat">
            <span className="stat-value">{formatPrice(stats.median)}</span>
            <span className="stat-label">median price</span>
          </div>
          {mySize ? (
            <div className="stat stat-highlight">
              <span className="stat-value">
                {stats.inSize}/{stats.count}
              </span>
              <span className="stat-label">in stock in your size ({mySize})</span>
            </div>
          ) : (
            <div className="stat">
              <span className="stat-value">{stats.availability}%</span>
              <span className="stat-label">of size slots in stock</span>
            </div>
          )}
        </div>
      )}

      <div className="toolbar">
        <input
          className="search"
          type="search"
          placeholder="Search hoodies, navy, baseball…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search products"
        />
        <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort products">
          <option value="name">Sort: Name (A–Z)</option>
          <option value="price-asc">Sort: Price (low → high)</option>
          <option value="price-desc">Sort: Price (high → low)</option>
          <option value="stock">Sort: Most in stock</option>
        </select>
      </div>

      <div className="my-size-bar">
        <span className="my-size-label">Shop my size:</span>
        {(['XS', 'S', 'M', 'L', 'XL', 'XXL'] as const).map((s) => (
          <button key={s} className={mySize === s ? 'size-pill active' : 'size-pill'} onClick={() => setMySize(mySize === s ? null : s)}>
            {s}
          </button>
        ))}
        {mySize && (
          <label className="only-my-size">
            <input type="checkbox" checked={onlyMySize} onChange={(e) => setOnlyMySize(e.target.checked)} />
            Only show what's in stock in {mySize}
          </label>
        )}
      </div>

      <div className="chips" role="group" aria-label="Filter by category">
        <button className={category === 'All' ? 'chip active' : 'chip'} onClick={() => setCategory('All')}>
          All <span className="chip-count">{products.length}</span>
        </button>
        {categories.map(([name, count]) => (
          <button key={name} className={category === name ? 'chip active' : 'chip'} onClick={() => setCategory(name)}>
            {name} <span className="chip-count">{count}</span>
          </button>
        ))}
      </div>

      {loading && <p className="muted">Loading products…</p>}
      {error && <p className="error-box">{error}</p>}
      {!loading && !error && visible.length === 0 && <p className="muted">No products match your search.</p>}

      <div className="product-grid stagger" key={`${category}-${query}-${sort}-${onlyMySize}`}>
        {visible.map((p, i) => (
          <ProductCard key={p.product_id} product={p} style={{ animationDelay: `${Math.min(i, 12) * 45}ms` }} />
        ))}
      </div>
    </section>
  )
}
