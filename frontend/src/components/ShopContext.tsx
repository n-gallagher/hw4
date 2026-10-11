import { createContext } from 'react'
import type { ProductSummary, Size } from '../api'

export interface BagItem {
  product: ProductSummary
  size: Size
  quantity: number
}

export interface ShopState {
  // Shopping bag (Problem 9, improvement 1)
  bag: BagItem[]
  units: number
  subtotal: number
  addToBag: (product: ProductSummary, size: Size, quantity: number) => { ok: boolean; message: string }
  setQuantity: (productId: string, size: Size, quantity: number) => void
  removeFromBag: (productId: string, size: Size) => void
  bagOpen: boolean
  openBag: () => void
  closeBag: () => void
  lastAdded: string | null // short confirmation shown in the drawer
  pawBurst: number // increases on every successful add (triggers Handsome Dan's paw-print burst)
  // "Shop my size" mode (Problem 9, improvement 2)
  mySize: Size | null
  setMySize: (size: Size | null) => void
}

export const ShopContext = createContext<ShopState | null>(null)

export const MAX_PER_LINE = 10

/** Most units of one product+size a shopper can hold: what's in stock, capped at 10. */
export const maxFor = (product: ProductSummary, size: Size) => Math.min(product.stock_by_size[size] ?? 0, MAX_PER_LINE)
