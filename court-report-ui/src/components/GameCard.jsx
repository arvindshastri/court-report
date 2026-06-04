import { useState } from 'react'

function parseScore(matchup) {
  // e.g. "New York Knicks 105  @  San Antonio Spurs 95"
  const atIdx = matchup.indexOf('@')
  if (atIdx === -1) return { label: matchup, winner: '', winnerScore: '', loser: '', loserScore: '' }

  const awayPart = matchup.slice(0, atIdx).trim()
  const homePart = matchup.slice(atIdx + 1).trim()

  const awayMatch = awayPart.match(/^(.*?)\s+(\d+)\s*$/)
  const homeMatch = homePart.match(/^(.*?)\s+(\d+)\s*$/)

  if (!awayMatch || !homeMatch) return { label: matchup, winner: awayPart, winnerScore: '', loser: homePart, loserScore: '' }

  const awayName = awayMatch[1].trim()
  const awayScore = parseInt(awayMatch[2])
  const homeName = homeMatch[1].trim()
  const homeScore = parseInt(homeMatch[2])

  const abbr = name => name.split(' ').map(w => w[0]).join('').slice(0, 3).toUpperCase()

  const awayWon = awayScore > homeScore
  const winName = awayWon ? awayName : homeName
  const winScore = awayWon ? awayScore : homeScore
  const losName = awayWon ? homeName : awayName
  const losScore = awayWon ? homeScore : awayScore

  return {
    label: `${awayName} @ ${homeName}`,
    winner: abbr(winName),
    winnerScore: winScore,
    loser: abbr(losName),
    loserScore: losScore,
  }
}

export default function GameCard({ game }) {
  const [open, setOpen] = useState(false)
  if (!game) return null

  const { label, winner, winnerScore, loser, loserScore } = parseScore(game.matchup)
  const hasRecap = !!game.card_recap

  return (
    <div className={`gcard${open ? ' open' : ''}`}>
      <div
        className="gcard-head"
        onClick={() => hasRecap && setOpen(o => !o)}
        style={{ cursor: hasRecap ? 'pointer' : 'default' }}
      >
        <div>
          <div className="g-label">{label}</div>
          <div className="g-score">
            <span className="g-w">{winner} <span className="g-win-score">{winnerScore}</span></span>
            {loser && <span className="g-sep">—</span>}
            {loser && <span className="g-l">{loser} <span className="g-los-score">{loserScore}</span></span>}
          </div>
        </div>
        {hasRecap && (
          <button className="g-btn">{open ? 'Close ↑' : 'Expand ↓'}</button>
        )}
      </div>
      {hasRecap && (
        <div className="gcard-body">
          <div className="gcard-inner">{game.card_recap}</div>
        </div>
      )}
    </div>
  )
}
