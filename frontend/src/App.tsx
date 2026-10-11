import { useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import NavBar from './components/NavBar'
import Footer from './components/Footer'
import ChatWidget from './components/ChatWidget'
import ChatResults from './components/ChatResults'
import ChatProvider from './components/ChatProvider'
import AuthProvider from './components/AuthProvider'
import ShopProvider from './components/ShopProvider'
import BagDrawer from './components/BagDrawer'
import RevealOnScroll from './components/RevealOnScroll'
import { useAuth } from './components/useAuth'
import Home from './pages/Home'
import Products from './pages/Products'
import ProductDetail from './pages/ProductDetail'
import About from './pages/About'
import Login from './pages/Login'
import CreateAccount from './pages/CreateAccount'
import Account from './pages/Account'
import NotFound from './pages/NotFound'

export default function App() {
  const { pathname } = useLocation()
  // On a product page the product comes first; chat results sit below it (so clicking a chat card visibly opens the item).
  const productPage = /^\/products\/[^/]+/.test(pathname)

  // Start every new page at the top.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <AuthProvider>
      <ShopProvider>
        <ChatProvider>
          <div className="app">
            <NavBar />
            <main className="main">
              {!productPage && <ChatResults />}
              {/* keyed by page so each route fades in (page transition) */}
              <div className="page-enter" key={pathname}>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/products" element={<Products />} />
                  <Route path="/products/:productId" element={<ProductDetail />} />
                  <Route path="/about" element={<About />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/create-account" element={<CreateAccount />} />
                  <Route path="/account" element={<Account />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </div>
              {productPage && <ChatResults />}
            </main>
            <RevealOnScroll />
            <Footer />
            <ChatForUser />
            <BagDrawer />
          </div>
        </ChatProvider>
      </ShopProvider>
    </AuthProvider>
  )
}

// A fresh chat per shopper: remount on login/logout so one person's conversation never shows for another.
function ChatForUser() {
  const { user, loading } = useAuth()
  if (loading) return null
  return <ChatWidget key={user?.id ?? 'guest'} />
}
