import { useEffect, useState, type ReactNode } from 'react'
import { formatPrice, type ProductSummary, type Size } from '../api'
import { maxFor, ShopContext, type BagItem } from './ShopContext'
import { useAuth } from './useAuth'

const SIZE_KEY = 'cc_my_size'

// Each shopper (or the guest) gets their own bag on this device.
const bagKey = (userId: number | undefined) => (userId ? `cc_bag_user_${userId}` : 'cc_bag_guest')

function loadBag(key: string): BagItem[] {
  try {
    const items = JSON.parse(localStorage.getItem(key) ?? '[]') as BagItem[]
    return Array.isArray(items) ? items.filter((i) => i?.product?.product_id && i.size && i.quantity > 0) : []
  } catch {
    return []
  }
}

export default function ShopProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const key = bagKey(user?.id)
  const [state, setState] = useState(() => ({ key, items: loadBag(key) }))
  const [bagOpen, setBagOpen] = useState(false)
  const [lastAdded, setLastAdded] = useState<string | null>(null)
  const [pawBurst, setPawBurst] = useState(0)
  const [mySize, setMySizeState] = useState<Size | null>(() => (localStorage.getItem(SIZE_KEY) as Size) || null)

  // Switch bags when the shopper logs in or out (adjusting state during render, per React docs).
  if (state.key !== key) setState({ key, items: loadBag(key) })

  useEffect(() => {
    localStorage.setItem(state.key, JSON.stringify(state.items))
  }, [state])

  const bag = state.items
  const setItems = (fn: (items: BagItem[]) => BagItem[]) => setState((s) => ({ ...s, items: fn(s.items) }))

  function addToBag(product: ProductSummary, size: Size, quantity: number) {
    const max = maxFor(product, size)
    const current = bag.find((i) => i.product.product_id === product.product_id && i.size === size)?.quantity ?? 0
    if (max === 0) return { ok: false, message: `${product.name} is sold out in ${size}.` }
    const add = Math.min(quantity, max - current)
    if (add <= 0) return { ok: false, message: `You already have all ${max} available in ${size}.` }
    setItems((items) => {
      const exists = items.some((i) => i.product.product_id === product.product_id && i.size === size)
      return exists
        ? items.map((i) =>
            i.product.product_id === product.product_id && i.size === size ? { ...i, quantity: i.quantity + add, product } : i,
          )
        : [...items, { product, size, quantity: add }]
    })
    const message = `Added ${add} × ${product.name} (${size}) · ${formatPrice(product.price * add)}`
    setLastAdded(message)
    setPawBurst((n) => n + 1)
    setBagOpen(true)
    return { ok: true, message }
  }

  const setQuantity = (productId: string, size: Size, quantity: number) =>
    setItems((items) =>
      items.map((i) =>
        i.product.product_id === productId && i.size === size
          ? { ...i, quantity: Math.max(1, Math.min(quantity, maxFor(i.product, size))) }
          : i,
      ),
    )

  const removeFromBag = (productId: string, size: Size) =>
    setItems((items) => items.filter((i) => !(i.product.product_id === productId && i.size === size)))

  const setMySize = (size: Size | null) => {
    setMySizeState(size)
    if (size) localStorage.setItem(SIZE_KEY, size)
    else localStorage.removeItem(SIZE_KEY)
  }

  const units = bag.reduce((n, i) => n + i.quantity, 0)
  const subtotal = bag.reduce((n, i) => n + i.quantity * i.product.price, 0)

  return (
    <ShopContext.Provider
      value={{
        bag,
        units,
        subtotal,
        addToBag,
        setQuantity,
        removeFromBag,
        bagOpen,
        openBag: () => setBagOpen(true),
        closeBag: () => {
          setBagOpen(false)
          setLastAdded(null)
        },
        lastAdded,
        pawBurst,
        mySize,
        setMySize,
      }}
    >
      {children}
    </ShopContext.Provider>
  )
}
