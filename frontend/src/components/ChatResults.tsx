import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice, getProducts } from '../api'
import ProductCard from './ProductCard'
import { useChat } from './useChat'

let lastScrolledId: number | undefined

// "From your chat": the products the agent picked (via show_products), rendered on the page
// as full product cards. Each card links to the same single-item page as the Products grid.
export default function ChatResults() {
  const { results, clearResults } = useChat()
  const ref = useRef<HTMLElement>(null)
  const resultsId = results?.id
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({})

  // Category sizes for the "See all N …" link (the agent shows at most 6 cards).
  useEffect(() => {
    getProducts()
      .then((all) => {
        const counts: Record<string, number> = {}
        all.forEach((p) => (counts[p.category] = (counts[p.category] ?? 0) + 1))
        setCategoryCounts(counts)
      })
      .catch(() => {})
  }, [])

  // Bring each new set of matches into view (once: not again when this section moves on a page change).
  useEffect(() => {
    if (resultsId && resultsId !== lastScrolledId) {
      lastScrolledId = resultsId
      ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [resultsId])

  if (!results || results.products.length === 0) return null

  const prices = results.products.map((p) => p.price)
  // All matches from one category → link to that whole aisle
  const categories = [...new Set(results.products.map((p) => p.category))]
  const category = categories.length === 1 ? categories[0] : null
  const total = category ? categoryCounts[category] : undefined
  const low = Math.min(...prices)
  const high = Math.max(...prices)

  return (
    <section ref={ref} className="chat-results" key={results.id} aria-label="Products from your chat">
      <div className="container">
        <div className="chat-results-head">
          <div>
            <p className="chat-results-eyebrow">
              <span className="pulse-dot" aria-hidden="true" /> From your chat
            </p>
            <h2>{results.query ? `“${results.query}”` : 'Picked for you'}</h2>
            <p className="chat-results-meta">
              {results.products.length} {results.products.length === 1 ? 'match' : 'matches'} ·{' '}
              {low === high ? formatPrice(low) : `${formatPrice(low)}–${formatPrice(high)}`} · live prices and stock
            </p>
          </div>
          <button className="chat-results-clear" onClick={clearResults} aria-label="Hide chat results">
            Clear ×
          </button>
        </div>

        {category && total && total > results.products.length && (
          <Link to={`/products?category=${encodeURIComponent(category)}`} className="see-all">
            See all {total} {category.toLowerCase()} →
          </Link>
        )}

        <div className="product-grid chat-results-grid">
          {results.products.map((p, i) => (
            <ProductCard key={p.product_id} product={p} style={{ animationDelay: `${i * 70}ms` }} />
          ))}
        </div>
      </div>
    </section>
  )
}
