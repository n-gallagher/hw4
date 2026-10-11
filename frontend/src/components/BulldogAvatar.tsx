// Handsome Dan, the Campus Customs bulldog concierge: a navy-and-gold bulldog drawn in SVG.
// Moods: happy (blinks, ear wiggles), thinking (head tilt), sleepy (closed eyes + zzz), sad (droopy brows).
export type DanMood = 'happy' | 'thinking' | 'sleepy' | 'sad'

export default function BulldogAvatar({
  size = 36,
  className = '',
  mood = 'happy',
}: {
  size?: number
  className?: string
  mood?: DanMood
}) {
  const closed = mood === 'sleepy'
  return (
    <svg
      className={`bulldog-avatar dan-${mood} ${className}`}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={`Handsome Dan the bulldog${mood === 'happy' ? '' : ` (${mood})`}`}
    >
      <circle cx="32" cy="32" r="31" fill="#00356b" stroke="#c9a227" strokeWidth="2" strokeDasharray="3 2.5" />
      <g className="dan-head">
        {/* ears */}
        <path className="dan-ear dan-ear-l" d="M13 20c-2-7 4-11 9-6l2 6z" fill="#e9dcc0" />
        <path className="dan-ear dan-ear-r" d="M51 20c2-7-4-11-9-6l-2 6z" fill="#e9dcc0" />
        {/* head */}
        <ellipse cx="32" cy="35" rx="19" ry="17" fill="#f3ead6" />
        {/* brows */}
        {mood === 'sad' ? (
          <path d="M21 26l7 2M43 26l-7 2" stroke="#8a7650" strokeWidth="1.8" strokeLinecap="round" />
        ) : (
          <path d="M24 24q8-4 16 0" stroke="#c9b48a" strokeWidth="1.6" fill="none" strokeLinecap="round" />
        )}
        {/* eyes */}
        {closed ? (
          <path d="M22 31q3 2 6 0M36 31q3 2 6 0" stroke="#1a1d24" strokeWidth="1.8" fill="none" strokeLinecap="round" />
        ) : (
          <g className="dan-eyes">
            <circle cx="25" cy="31" r="2.6" fill="#1a1d24" />
            <circle cx="39" cy="31" r="2.6" fill="#1a1d24" />
            <circle cx="25.8" cy="30.2" r="0.8" fill="#fff" />
            <circle cx="39.8" cy="30.2" r="0.8" fill="#fff" />
          </g>
        )}
        {/* muzzle, nose, mouth */}
        <ellipse cx="32" cy="41" rx="10" ry="7.5" fill="#e9dcc0" />
        <ellipse cx="32" cy="37.5" rx="4" ry="2.8" fill="#1a1d24" />
        {mood === 'sad' ? (
          <path d="M27 45q5-3 10 0" stroke="#1a1d24" strokeWidth="1.6" fill="none" strokeLinecap="round" />
        ) : (
          <>
            <path d="M26 43q6 5 12 0" stroke="#1a1d24" strokeWidth="1.6" fill="none" strokeLinecap="round" />
            {/* underbite teeth */}
            <path d="M28.5 43.2v2M35.5 43.2v2" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
          </>
        )}
        {/* collar + tag */}
        <path d="M17 50q15 9 30 0" stroke="#c9a227" strokeWidth="3" fill="none" />
        <circle cx="32" cy="55" r="3" fill="#c9a227" />
      </g>
      {closed && (
        <text className="dan-zzz" x="47" y="16" fontSize="10" fontWeight="700" fill="#f2e3b3">
          z
        </text>
      )}
    </svg>
  )
}

/** A single paw print (Handsome Dan's), used for trails and the "added to bag" burst. */
export function PawPrint({ size = 16, color = '#c9a227', className = '' }: { size?: number; color?: string; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <ellipse cx="12" cy="16" rx="5.2" ry="4.4" fill={color} />
      <ellipse cx="5.2" cy="10.2" rx="2.2" ry="2.8" fill={color} />
      <ellipse cx="9.4" cy="6.2" rx="2.2" ry="2.9" fill={color} />
      <ellipse cx="14.6" cy="6.2" rx="2.2" ry="2.9" fill={color} />
      <ellipse cx="18.8" cy="10.2" rx="2.2" ry="2.8" fill={color} />
    </svg>
  )
}
