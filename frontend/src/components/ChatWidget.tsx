import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  ApiError,
  formatPrice,
  getChatHistory,
  sendChat,
  type ChatTurn,
  type FactCheck,
  type HistoryMessage,
  type ProductSummary,
  type User,
} from '../api'
import { useAuth } from './useAuth'
import { useChat } from './useChat'
import { useShop } from './useShop'
import BulldogAvatar from './BulldogAvatar'

interface Message {
  role: 'user' | 'assistant'
  content: string
  products?: ProductSummary[]
  query?: string // the question that produced these products
  verified?: FactCheck | null // price & stock fact-checker result
  added?: number // items the agent put in the bag
  error?: boolean
}

const HISTORY_TURNS = 12 // guests: earlier messages sent with each request so the agent remembers the conversation

// Guests only (logged-in history is read from the database on the server). Product ids shown as
// cards are noted so follow-ups like "is the first one in medium?" still work. Errors and the
// welcome message are left out.
function toHistory(messages: Message[]): ChatTurn[] {
  return messages
    .slice(1)
    .filter((m) => !m.error)
    .slice(-HISTORY_TURNS)
    .map((m) => ({
      role: m.role,
      content: m.products?.length
        ? `${m.content}
[Products shown: ${m.products.map((p) => p.product_id).join(', ')}]`
        : m.content,
    }))
}

function welcome(user: User | null, returning: boolean): Message {
  const content = !user
    ? 'Woof! I’m Handsome Dan, Yale’s bulldog and your shop concierge 🐾 Ask me about products, prices, colors or sizes in stock, and I can put things in your bag.'
    : returning
      ? `Welcome back, ${user.first_name}! Your earlier chat is below. What can I help you find today?`
      : `Woof, hi ${user.first_name}! I’m Handsome Dan, your bulldog concierge 🐾 Your chat is saved to your account, so you can pick up where you left off.`
  return { role: 'assistant', content }
}

// Saved messages -> chat bubbles; cards shown with a reply remember the question that produced them.
function fromHistory(saved: HistoryMessage[]): Message[] {
  return saved.map((m, i) => ({
    role: m.role,
    content: m.content,
    products: m.products,
    query: m.role === 'assistant' && i > 0 && saved[i - 1].role === 'user' ? saved[i - 1].content : undefined,
  }))
}

// Show **bold** from the model as bold instead of raw asterisks (everything else stays plain text).
function renderText(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )
}

// What Dan is "doing" while the agent works (one picked per message).
const THINKING = ['Sniffing the stockroom', 'Fetching the details', 'Checking every shelf', 'Nose to the inventory']

// Quick-reply chips that change with the page the shopper is on.
function suggestionsFor(onProduct: boolean, onProducts: boolean, mySize: string | null, bagCount: number): string[] {
  const chips = onProduct
    ? [
        mySize ? `Is this in stock in ${mySize}?` : 'Which sizes are in stock?',
        'Show me similar styles under $60',
        mySize ? `Add this in ${mySize} to my bag` : 'What colors does this come in?',
      ]
    : onProducts
      ? ['What hoodies do you have?', 'Navy tees under $40', 'Best gift under $50?']
      : ['What hoodies do you have?', 'Navy tees under $40', 'Gift ideas for Family Weekend']
  return bagCount > 0 ? [...chips, 'Is everything in my bag in stock?'] : chips
}

export default function ChatWidget() {
  const { isOpen, draft, setDraft, openChat, closeChat, showResults } = useChat()
  const { user } = useAuth()
  const { bag, mySize, addToBag, openBag } = useShop()
  // App remounts this widget (key = user id) on login/logout, so state always belongs to one shopper.
  const [messages, setMessages] = useState<Message[]>([welcome(user, false)])
  const [loadingHistory, setLoadingHistory] = useState(Boolean(user))
  const [sending, setSending] = useState(false)
  const [thinking, setThinking] = useState(THINKING[0])
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const { pathname } = useLocation()
  const productMatch = pathname.match(/^\/products\/([^/]+)$/)
  const currentProductId = productMatch ? decodeURIComponent(productMatch[1]) : null

  // Customer memory: a returning logged-in shopper gets their saved conversation back.
  useEffect(() => {
    if (!user) return
    getChatHistory()
      .then((res) => {
        if (res.logged_in && res.messages.length > 0) {
          setMessages([welcome(user, true), ...fromHistory(res.messages)])
        }
      })
      .catch(() => {})
      .finally(() => setLoadingHistory(false))
  }, [user])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending, isOpen])

  useEffect(() => {
    if (isOpen) inputRef.current?.focus()
  }, [isOpen])

  async function send(text: string) {
    const message = text.trim()
    if (!message || sending) return
    const history = toHistory(messages)
    setMessages((m) => [...m, { role: 'user', content: message }])
    setDraft('')
    setThinking(THINKING[messages.length % THINKING.length]) // a different caption each turn
    setSending(true)
    try {
      const res = await sendChat(
        message,
        user ? [] : history,
        { path: pathname, productId: currentProductId },
        { bag: bag.map((i) => ({ product_id: i.product.product_id, size: i.size, quantity: i.quantity })), mySize },
      )
      // Agent's add_to_bag results (already stock-checked on the server) go into the bag, which slides open
      res.bag_additions.forEach((a) => addToBag(a.product, a.size, a.quantity))
      const added = res.bag_additions.reduce((n, a) => n + a.quantity, 0)
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: res.reply, products: res.products, query: message, verified: res.verified, added },
      ])
      // API contract: the agent's structured matches (res.products) become product cards on the page
      // ...unless the reply is only about items the agent just put in the bag: the bag drawer already shows those
      const bagOnly =
        res.bag_additions.length > 0 &&
        res.products.every((p) => res.bag_additions.some((a) => a.product.product_id === p.product_id))
      if (res.products.length > 0 && !bagOnly) showResults(message, res.products)
    } catch (err) {
      const content =
        err instanceof ApiError && err.status === 503
          ? err.message
          : 'Sorry, I couldn’t reach the shop server. Please try again in a moment.'
      setMessages((m) => [...m, { role: 'assistant', content, error: true }])
    } finally {
      setSending(false)
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    send(draft)
  }

  if (!isOpen) {
    return (
      // Handsome Dan himself is the chat button: click him and the chat opens right where he sits.
      <button className="dan-launcher" onClick={() => openChat()} aria-label="Chat with Handsome Dan, the bulldog concierge">
        <span className="dan-bubble">Woof! Need a paw?</span>
        <BulldogAvatar size={84} />
      </button>
    )
  }

  return (
    <aside className="chat-panel" aria-label="Campus Customs assistant">
      <header className="chat-header">
        <BulldogAvatar size={40} className="header-avatar" mood={sending ? 'thinking' : 'happy'} />
        <div>
          <strong>Handsome Dan</strong>
          <span className="chat-status">
            {user ? `Signed in as ${user.first_name} · chat saved` : 'Guest · log in to save this chat'}
          </span>
        </div>
        <button className="chat-close" onClick={closeChat} aria-label="Close chat">
          ×
        </button>
      </header>

      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chat-row ${m.role}`}>
          {m.role === 'assistant' && <BulldogAvatar size={28} className="msg-avatar" />}
          <div className={`chat-msg ${m.role}${m.error ? ' error' : ''}`}>
            <p>{renderText(m.content)}</p>
            {m.added ? <span className="bag-pill">🛍 Added {m.added} to your bag</span> : null}
            {m.verified && m.verified.prices_checked + m.verified.stock_counts_checked > 0 && (
              <span
                className="verified-badge"
                title="Every price and stock number in this reply was checked against the live inventory database"
              >
                ✓ {[
                  m.verified.prices_checked && `${m.verified.prices_checked} price${m.verified.prices_checked > 1 ? 's' : ''}`,
                  m.verified.stock_counts_checked &&
                    `${m.verified.stock_counts_checked} stock count${m.verified.stock_counts_checked > 1 ? 's' : ''}`,
                ]
                  .filter(Boolean)
                  .join(' · ')}{' '}
                verified{m.verified.retries ? ` · auto-corrected ${m.verified.retries}×` : ''}
              </span>
            )}
            {m.products && m.products.length > 0 && (
              <div className="chat-products">
                <div className="chat-thumbs">
                  {m.products.map((p) => (
                    <Link key={p.product_id} to={`/products/${p.product_id}`} title={`${p.name} · ${formatPrice(p.price)}`}>
                      <img src={p.image_url} alt={p.name} />
                    </Link>
                  ))}
                </div>
                <button
                  className="chat-view-page"
                  // re-showing bumps the results id, so the page scrolls to the cards; bag adds open the bag instead
                  onClick={() => (m.added ? openBag() : showResults(m.query ?? '', m.products ?? []))}
                >
                  {m.added
                    ? 'View your bag →'
                    : `${m.products.length} ${m.products.length === 1 ? 'item' : 'items'} on the page ↑`}
                </button>
              </div>
            )}
          </div>
          </div>
        ))}
        {(loadingHistory || sending) && (
          <div className="chat-row assistant">
            <BulldogAvatar size={28} className="msg-avatar" mood="thinking" />
            <div className="chat-msg assistant typing" aria-label={loadingHistory ? 'Loading your saved chat' : 'Thinking'}>
              <span className="dots">
                <i />
                <i />
                <i />
              </span>
              <small>{loadingHistory ? 'Fetching your saved chat' : `${thinking}…`}</small>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {!sending && (
        <div className="chat-suggestions">
          {suggestionsFor(Boolean(currentProductId), pathname === '/products', mySize, bag.length).map((s) => (
            <button key={s} onClick={() => send(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about merch, prices, sizes…"
          aria-label="Chat message"
        />
        <button type="submit" disabled={!draft.trim() || sending}>
          Send
        </button>
      </form>
    </aside>
  )
}
