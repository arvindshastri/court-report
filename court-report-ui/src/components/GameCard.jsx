import { useState } from 'react'

function ChevronUp() {
  return (
    <svg width="13" height="8" viewBox="0 0 13 8" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M1.5 6.5L6.5 1.5L11.5 6.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function ChevronDown() {
  return (
    <svg width="13" height="8" viewBox="0 0 13 8" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M1.5 1.5L6.5 6.5L11.5 1.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

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

function TeamLogo({ teamId, size = 32 }) {
  const [hidden, setHidden] = useState(false)
  if (!teamId || hidden) return null
  return (
    <img
      className="team-logo"
      src={`https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg`}
      alt=""
      width={size}
      height={size}
      onError={() => setHidden(true)}
    />
  )
}

function quarterLabels(count) {
  return Array.from({ length: count }, (_, i) => (i < 4 ? `Q${i + 1}` : `OT${i - 3}`))
}

function QuarterTable({ home, away }) {
  if (!home?.quarters?.length && !away?.quarters?.length) return null
  const periods = Math.max(home?.quarters?.length || 0, away?.quarters?.length || 0)
  const labels = quarterLabels(periods)

  return (
    <table className="qtr-table">
      <thead>
        <tr>
          <th></th>
          {labels.map(l => <th key={l}>{l}</th>)}
          <th>T</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td className="qtr-tri">
            {away?.tricode}
            {away?.wins != null && <span className="qtr-record">{away.wins}-{away.losses}</span>}
          </td>
          {labels.map((_, i) => <td key={i}>{away?.quarters?.[i] ?? '—'}</td>)}
          <td className="qtr-total">{away?.score}</td>
        </tr>
        <tr>
          <td className="qtr-tri">
            {home?.tricode}
            {home?.wins != null && <span className="qtr-record">{home.wins}-{home.losses}</span>}
          </td>
          {labels.map((_, i) => <td key={i}>{home?.quarters?.[i] ?? '—'}</td>)}
          <td className="qtr-total">{home?.score}</td>
        </tr>
      </tbody>
    </table>
  )
}

function teamForName(teamName, game) {
  if (game?.home_team?.name === teamName) return game.home_team
  if (game?.away_team?.name === teamName) return game.away_team
  return null
}

function formatPct(p) {
  if (p === null || p === undefined) return '—'
  return `${(p * 100).toFixed(1)}%`
}

function TopPlayersTable({ players, game }) {
  if (!players?.length) return null
  return (
    <table className="tp-table">
      <thead>
        <tr>
          <th className="tp-th-name">Player</th>
          <th>MIN</th>
          <th>PTS</th>
          <th>REB</th>
          <th>AST</th>
          <th>STL</th>
          <th>BLK</th>
          <th>FG%</th>
          <th>+/-</th>
          <th>GmSc</th>
        </tr>
      </thead>
      <tbody>
        {players.map((p, i) => {
          const team = teamForName(p.team, game)
          return (
            <tr key={i}>
              <td className="tp-name">
                {team && <TeamLogo teamId={team.team_id} size={20} />}
                <span>{p.name}</span>
              </td>
              <td>{p.minutes ?? '—'}</td>
              <td>{p.pts ?? '—'}</td>
              <td>{p.reb ?? '—'}</td>
              <td>{p.ast ?? '—'}</td>
              <td>{p.stl ?? '—'}</td>
              <td>{p.blk ?? '—'}</td>
              <td>{formatPct(p.fg_pct)}</td>
              <td className={p.plus_minus > 0 ? 'tp-pos' : p.plus_minus < 0 ? 'tp-neg' : ''}>
                {p.plus_minus > 0 ? `+${p.plus_minus}` : p.plus_minus ?? '—'}
              </td>
              <td className="tp-gmsc">{p.game_score ?? '—'}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export default function GameCard({ game }) {
  const [open, setOpen] = useState(false)
  if (!game) return null

  const { label, winner, winnerScore, loser, loserScore } = parseScore(game.matchup)
  const hasRecap = !!game.card_recap
  const home = game.home_team
  const away = game.away_team
  const hasQuarters = !!(home?.quarters?.length || away?.quarters?.length)
  const hasTopPlayers = !!(game.top_players && game.top_players.length)
  const expandable = hasRecap || hasQuarters || hasTopPlayers

  let winnerTeam = null
  let loserTeam = null
  if (home && away) {
    const homeWon = (home.score ?? 0) > (away.score ?? 0)
    winnerTeam = homeWon ? home : away
    loserTeam = homeWon ? away : home
  }

  return (
    <div className={`gcard${open ? ' open' : ''}`}>
      <div
        className="gcard-head"
        onClick={() => expandable && setOpen(o => !o)}
        style={{ cursor: expandable ? 'pointer' : 'default' }}
      >
        <div>
          <div className="g-label">{label}</div>
          <div className="g-score">
            <span className="g-w">
              {winnerTeam && <TeamLogo teamId={winnerTeam.team_id} />}
              {winner} <span className="g-win-score">{winnerScore}</span>
            </span>
            {loser && <span className="g-sep">—</span>}
            {loser && (
              <span className="g-l">
                {loserTeam && <TeamLogo teamId={loserTeam.team_id} />}
                {loser} <span className="g-los-score">{loserScore}</span>
              </span>
            )}
          </div>
        </div>
        {expandable && (
          <button className="g-btn" aria-label={open ? 'Collapse game card' : 'Expand game card'}>
            {open ? <ChevronUp /> : <ChevronDown />}
          </button>
        )}
      </div>
      {expandable && (
        <div className="gcard-body">
          <div className="gcard-inner">
            {hasRecap && <div>{game.card_recap}</div>}
            <QuarterTable home={home} away={away} />
            <TopPlayersTable players={game.top_players} game={game} />
          </div>
        </div>
      )}
    </div>
  )
}
