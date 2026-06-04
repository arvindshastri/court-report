export default function Ticker({ games = [] }) {
  const items = games.map(g => {
    const parts = [g.matchup]
    if (g.final_score) parts.push(g.final_score)
    if (g.key_stats) parts.push(...g.key_stats)
    return parts.join(' · ')
  }).join(' ★ ')

  const text = items ? `★ ${items}` : '★ NBA Court Report — Loading...'

  return (
    <div className="ticker">
      <span className="ticker-inner">{text}</span>
    </div>
  )
}
