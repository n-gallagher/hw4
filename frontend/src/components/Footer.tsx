import { Link } from 'react-router-dom'

const YEAR = new Date().getFullYear()

// Pennant-style footer (varsity design).
export default function Footer() {
  return (
    <footer className="footer varsity-footer">
      <div className="footer-stripes" aria-hidden="true" />
      <div className="footer-inner">
        <div className="pennant" aria-hidden="true">
          <span>Campus Customs</span>
        </div>
        <div className="footer-cols">
          <div>
            <h4>Visit</h4>
            <p>57 Broadway, New Haven, CT</p>
            <p>Online as Yale Bulldog Blue</p>
          </div>
          <div>
            <h4>Shop</h4>
            <p>
              <Link to="/products">All products</Link>
            </p>
            <p>
              <Link to="/products?category=Hoodies">Hoodies</Link> · <Link to="/products?category=T-Shirts">Tees</Link>
            </p>
          </div>
          <div>
            <h4>Promise</h4>
            <p>Officially licensed Yale apparel</p>
            <p>Live prices &amp; stock, checked by our concierge</p>
          </div>
        </div>
      </div>
      <div className="footer-base">© {YEAR} Campus Customs · New Haven, CT · Boola Boola</div>
    </footer>
  )
}
