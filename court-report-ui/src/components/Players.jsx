function parsePlayer(str) {
  if (!str) return null
  // e.g. "🏆 Jalen Brunson — 30 PTS, 3 REB, 2 AST | reason text"
  const pipeIdx = str.indexOf('|')
  const left = pipeIdx !== -1 ? str.slice(0, pipeIdx).trim() : str.trim()
  const reason = pipeIdx !== -1 ? str.slice(pipeIdx + 1).trim() : ''

  // Strip leading emoji + badge
  const dashIdx = left.indexOf('—')
  const name = dashIdx !== -1
    ? left.slice(0, dashIdx).replace(/^[^\w]+/, '').trim()
    : left.replace(/^[^\w]+/, '').trim()

  const statsRaw = dashIdx !== -1 ? left.slice(dashIdx + 1).trim() : ''

  // Parse stat tokens like "30 PTS, 3 REB, 2 AST, +22 +/-"
  const stats = []
  const tokens = statsRaw.split(',').map(s => s.trim())
  for (const t of tokens) {
    const parts = t.split(/\s+/)
    if (parts.length >= 2) {
      stats.push({ val: parts[0], label: parts.slice(1).join(' ') })
    }
  }

  return { name, reason: reason.replace(/^Underrated:\s*/i, ''), stats: stats.slice(0, 5) }
}

function PlayerCard({ raw, variant }) {
  const player = parsePlayer(raw)
  if (!player) return null

  const isTop = variant === 'top'

  return (
    <div className={`p-card ${isTop ? 'top' : 'und'}`}>
      <div className="p-left">
        <div className={`p-badge ${isTop ? 'gold' : 'teal'}`}>
          {isTop ? '🏆 Player of the Night' : '⭐ Most Underrated'}
        </div>
        <div className="p-name">{player.name}</div>
        <div className="p-why">{player.reason}</div>
      </div>
      <div className="p-stats">
        {player.stats.map((s, i) => (
          <div className="s-blk" key={i}>
            <div className="s-n">{s.val}</div>
            <div className="s-l">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Players({ players = {} }) {
  if (!players.top && !players.underrated) return null

  return (
    <div className="players">
      <div className="rh">
        <span className="rh-label">Players of the Night</span>
        <div className="rh-line"></div>
      </div>
      <PlayerCard raw={players.top} variant="top" />
      <PlayerCard raw={players.underrated} variant="underrated" />
    </div>
  )
}
