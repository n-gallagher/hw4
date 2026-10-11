import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice, getProducts, type ProductSummary } from '../api'
import { PawPrint } from '../components/BulldogAvatar'

// Real products fanned in the hero (picked from the catalogue, one per category).
const HERO_PICKS = ['basic-hoodie-big-yale', '2025-yale-vs-harvard-t-shirt', 'yale-law-school-1-4-zip']

const CATEGORIES = [
  { name: 'Hoodies', blurb: 'Heavyweight & warm' },
  { name: 'Crewnecks', blurb: 'The classic sweatshirt' },
  { name: 'T-Shirts', blurb: 'Game day to every day' },
  { name: 'Quarter-zips', blurb: 'Interview-ready layer' },
  { name: 'Fleece & Jackets', blurb: 'For November in New Haven' },
  { name: 'Long Sleeve', blurb: 'Light layers' },
]

const highlights = [
  {
    title: 'Hoodies & crewnecks',
    text: 'Heavy, warm layers for those late walks home from Sterling and the Game in November.',
  },
  {
    title: 'Tees for every day',
    text: 'Easy everyday shirts, from classic YALE lettering to rivalry graphics.',
  },
  {
    title: 'Quarter-zips & fleece',
    text: 'Polished enough for a case interview, comfy enough for a study session.',
  },
]

export default function Home() {
  const [products, setProducts] = useState<ProductSummary[]>([])

  useEffect(() => {
    getProducts()
      .then(setProducts)
      .catch(() => setProducts([]))
  }, [])

  const heroProducts = HERO_PICKS.map((id) => products.find((p) => p.product_id === id)).filter(
    (p): p is ProductSummary => Boolean(p),
  )
  const countBy = (cat: string) => products.filter((p) => p.category === cat).length
  const fromPrice = (cat: string) => {
    const prices = products.filter((p) => p.category === cat).map((p) => p.price)
    return prices.length ? Math.min(...prices) : null
  }

  return (
    <>
      <section className="hero varsity-hero">
        <div className="hero-inner">
          <div className="hero-copy">
            <p className="stamp">Est. New Haven · 57 Broadway</p>
            <h1>
              Wear your
              <br />
              <span className="hero-accent">Bulldog blue.</span>
            </h1>
            <p className="hero-sub">
              Campus Customs is your go-to for Yale gear that actually feels good to wear. Find a hoodie for the
              dining hall, a tee for game day, or a gift for the family heading up for Family Weekend.
            </p>
            <div className="hero-actions">
              <Link to="/products" className="btn btn-gold">
                ★ Shop the collection
              </Link>
              <Link to="/about" className="btn btn-outline">
                Our story
              </Link>
            </div>
            <p className="hero-proof">Officially licensed · {products.length || 100}+ styles · XS–XXL</p>
          </div>

          <div className="hero-fan" aria-label="Featured products">
            {heroProducts.map((p, i) => (
              <Link key={p.product_id} to={`/products/${p.product_id}`} className={`fan-card fan-${i}`}>
                <img src={p.image_url} alt={p.name} />
                <span className="fan-label">
                  {p.name}
                  <strong>{formatPrice(p.price)}</strong>
                </span>
              </Link>
            ))}
          </div>
        </div>
        {/* a trail of Dan's paw prints walking across the page */}
        <div className="paw-trail" aria-hidden="true">
          {Array.from({ length: 14 }, (_, i) => (
            <PawPrint key={i} size={18} className={i % 2 ? 'paw-up' : 'paw-down'} />
          ))}
        </div>
      </section>

      <section className="section container">
        <div className="section-head reveal">
          <p className="eyebrow eyebrow-dark">Shop by category</p>
          <h2>Pick your letter</h2>
        </div>
        <div className="patch-grid">
          {CATEGORIES.map((c, i) => (
            <Link
              key={c.name}
              to={`/products?category=${encodeURIComponent(c.name)}`}
              className="patch reveal"
              style={{ transitionDelay: `${i * 60}ms` }}
            >
              <span className="patch-name">{c.name}</span>
              <span className="patch-blurb">{c.blurb}</span>
              {products.length > 0 && (
                <span className="patch-meta">
                  {countBy(c.name)} styles · from {formatPrice(fromPrice(c.name) ?? 0)}
                </span>
              )}
            </Link>
          ))}
        </div>
      </section>

      <section className="section container">
        <div className="section-head reveal">
          <p className="eyebrow eyebrow-dark">Why Campus Customs</p>
          <h2>Made for campus life</h2>
        </div>
        <div className="card-grid">
          {highlights.map((h, i) => (
            <div key={h.title} className="info-card reveal" style={{ transitionDelay: `${i * 80}ms` }}>
              <h3>{h.title}</h3>
              <p>{h.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section container callout reveal">
        <div>
          <h2>Not sure what to pick?</h2>
          <p>
            Ask Handsome Dan, our bulldog concierge (bottom right). Tell him what you're looking for and he'll point you to the right
            piece, with real prices and sizes in stock, and he can put it straight in your bag.
          </p>
        </div>
        <Link to="/products" className="btn btn-primary">
          Browse products
        </Link>
      </section>
    </>
  )
}
