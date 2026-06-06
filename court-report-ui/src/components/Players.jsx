import { useState } from 'react'

function parsePlayer(str) {
  if (!str) return null
  // e.g. "🏆 Jalen Brunson — 30 PTS, 3 REB, 2 AST | reason text"

  // Split on ' | ' first to isolate stats side from reason
  const pipeIdx = str.indexOf(' | ')
  const left   = pipeIdx !== -1 ? str.slice(0, pipeIdx).trim() : str.trim()
  const reason = pipeIdx !== -1 ? str.slice(pipeIdx + 3).trim() : ''

  // Strip leading emoji/badge, split on ' — ' to get name vs stats
  const dashIdx = left.indexOf(' — ')
  const name = dashIdx !== -1
    ? left.slice(0, dashIdx).replace(/^[^\w]+/, '').trim()
    : left.replace(/^[^\w]+/, '').trim()

  // Everything after ' — ', then drop any trailing " on X% FG"-style clause
  const statsRaw = dashIdx !== -1
    ? left.slice(dashIdx + 3).replace(/\s+on\s+[\d.]+%[^,]*/gi, '').trim()
    : ''

  // Parse stat tokens like "30 PTS, 3 REB, 2 AST, +22 +/-"
  const stats = []
  const tokens = statsRaw.split(',').map(s => s.trim()).filter(Boolean)
  for (const t of tokens) {
    const parts = t.split(/\s+/)
    if (parts.length >= 2) {
      stats.push({ val: parts[0], label: parts.slice(1).join(' ') })
    }
  }

  return { name, reason: reason.replace(/^Underrated:\s*/i, ''), stats: stats.slice(0, 5) }
}

function findPersonId(name, games) {
  if (!name || !games?.length) return null
  const norm = s => s.toLowerCase().replace(/[^a-z\s]/g, '').trim()
  const target = norm(name)
  for (const g of games) {
    for (const p of g.top_players || []) {
      if (norm(p.name) === target) return p.person_id
    }
  }
  // fall back to a loose contains match
  for (const g of games) {
    for (const p of g.top_players || []) {
      const pn = norm(p.name)
      if (pn.includes(target) || target.includes(pn)) return p.person_id
    }
  }
  return null
}

function initials(name) {
  if (!name) return '?'
  return name.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

function Headshot({ personId, name, size = 48 }) {
  const [failed, setFailed] = useState(false)

  if (!personId || failed) {
    return (
      <div className="p-headshot p-headshot-fallback" style={{ width: size, height: size }}>
        {initials(name)}
      </div>
    )
  }

  return (
    <img
      className="p-headshot"
      src={`https://cdn.nba.com/headshots/nba/latest/260x190/${personId}.png`}
      alt={name}
      width={size}
      height={size}
      onError={() => setFailed(true)}
    />
  )
}

function PlayerCard({ raw, variant, games }) {
  const player = parsePlayer(raw)
  if (!player) return null

  const isTop = variant === 'top'
  const personId = findPersonId(player.name, games)

  return (
    <div className={`p-card ${isTop ? 'top' : 'und'}`}>
      <div className="p-left">
        <div className="p-head-row">
          <Headshot personId={personId} name={player.name} />
          <div>
            <div className={`p-badge ${isTop ? 'gold' : 'teal'}`}>
              {isTop ? '🏆 Player of the Night' : '⭐ Most Underrated'}
            </div>
            <div className="p-name">{player.name}</div>
          </div>
        </div>
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

export default function Players({ players = {}, games = [] }) {
  if (!players.top && !players.underrated) return null

  return (
    <div className="players">
      <div className="rh">
        <span className="rh-label">Players of the Night</span>
        <div className="rh-line"></div>
      </div>
      <PlayerCard raw={players.top} variant="top" games={games} />
      <PlayerCard raw={players.underrated} variant="underrated" games={games} />
    </div>
  )
}
