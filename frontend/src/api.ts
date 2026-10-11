// Typed client for the Campus Customs FastAPI backend (proxied by Vite).

export type StockStatus = 'in_stock' | 'low' | 'sold_out'

export interface SizeStock {
  size: string
  quantity: number
  status: StockStatus
}

export interface ProductSummary {
  product_id: string
  name: string
  garment_type: string
  category: string
  short_description: string
  price: number
  colors: string[]
  image_url: string
  total_stock: number
  sizes_in_stock: number
  sizes_total: number
  stock_by_size: Record<string, number> // units per size, e.g. { XS: 0, M: 12 }
}

export const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL'] as const
export type Size = (typeof SIZES)[number]

export interface BagLine {
  product_id: string
  size: Size
  quantity: number
}

export interface FactCheck {
  prices_checked: number
  stock_counts_checked: number
  retries: number
}

export interface ProductDetail extends ProductSummary {
  description: string
  search_tags: string[]
  sizes: SizeStock[]
}

export interface ChatResponse {
  reply: string
  products: ProductSummary[]
  bag_additions: { product: ProductSummary; size: Size; quantity: number }[] // items the agent added to the bag
  verified: FactCheck | null // price & stock fact-checker result
}

export interface User {
  id: number
  first_name: string
  last_name: string
  email: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { credentials: 'same-origin', ...init })
  if (!res.ok) {
    let message = res.status === 404 ? 'Not found' : `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string' && res.status !== 404) message = body.detail
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

const postJson = <T,>(url: string, body: unknown) =>
  request<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const getMe = () => request<User>('/api/auth/me')

export const login = (email: string, password: string) => postJson<User>('/api/auth/login', { email, password })

export const signup = (form: {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}) => postJson<User>('/api/auth/signup', form)

export const logout = () => postJson<void>('/api/auth/logout', {})

export const getProducts = () => request<ProductSummary[]>('/api/products')

export const getProduct = (id: string) =>
  request<ProductDetail>(`/api/products/${encodeURIComponent(id)}`)

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

// Page context sent with every message, so "do you have this in pink?" refers to the product on screen.
export interface PageInfo {
  path: string
  productId: string | null
}

export const sendChat = (
  message: string,
  history: ChatTurn[],
  page: PageInfo,
  shop: { bag: BagLine[]; mySize: Size | null },
) =>
  postJson<ChatResponse>('/api/chat', {
    message,
    history, // used for guests only; logged-in history comes from the database
    page_path: page.path,
    current_product_id: page.productId,
    bag: shop.bag, // so the agent knows what's in the bag (and add_to_bag respects stock)
    my_size: shop.mySize,
  })

export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
  products: ProductSummary[]
  created_at: string
}

export const getChatHistory = () =>
  request<{ logged_in: boolean; messages: HistoryMessage[] }>('/api/chat/history')

export const formatPrice = (price: number) =>
  price.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 })
