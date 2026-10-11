import { createContext } from 'react'
import type { ProductSummary } from '../api'

// Product matches from the latest agent reply, shown as cards on the page.
export interface ChatResults {
  id: number // increases with every new set, so the page can animate and scroll to it
  query: string // what the shopper asked
  products: ProductSummary[]
}

export interface ChatState {
  isOpen: boolean
  draft: string
  setDraft: (text: string) => void
  openChat: (prefill?: string) => void
  closeChat: () => void
  results: ChatResults | null
  showResults: (query: string, products: ProductSummary[]) => void
  clearResults: () => void
}

export const ChatContext = createContext<ChatState | null>(null)
