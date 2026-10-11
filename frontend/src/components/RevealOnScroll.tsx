import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

// Motion: anything with class "reveal" fades up the first time it scrolls into view.
// One observer for the whole app; re-scans when the page changes or new content renders.
export default function RevealOnScroll() {
  const { pathname } = useLocation()

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('in')
            io.unobserve(e.target)
          }
        }),
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    )
    // Already on screen → show right away (never leave content hidden); below the fold → reveal on scroll.
    const scan = () =>
      document.querySelectorAll('.reveal:not(.in)').forEach((el) => {
        if (el.getBoundingClientRect().top < (window.innerHeight || document.documentElement.clientHeight)) el.classList.add('in')
        else io.observe(el)
      })
    scan()
    const mo = new MutationObserver(scan)
    mo.observe(document.body, { childList: true, subtree: true })
    window.addEventListener('scroll', scan, { passive: true }) // fallback where the observer is throttled
    return () => {
      io.disconnect()
      mo.disconnect()
      window.removeEventListener('scroll', scan)
    }
  }, [pathname])

  return null
}
