import { useState, useEffect } from 'react'

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']

function parseGameDateTime(text) {
  if (!text) return null

  const monthPattern = MONTHS.join('|')
  const dateMatch = text.match(new RegExp(`(${monthPattern})\\s+(\\d{1,2})(?:st|nd|rd|th)?`, 'i'))
  if (!dateMatch) return null

  const timeMatch = text.match(/(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?/i)

  const month = MONTHS.findIndex(m => m.toLowerCase() === dateMatch[1].toLowerCase())
  const day = parseInt(dateMatch[2], 10)

  let hours = 19 // default to 7pm if no time found
  let minutes = 0
  if (timeMatch) {
    hours = parseInt(timeMatch[1], 10)
    minutes = timeMatch[2] ? parseInt(timeMatch[2], 10) : 0
    const isPM = timeMatch[3].toLowerCase() === 'p'
    if (isPM && hours !== 12) hours += 12
    if (!isPM && hours === 12) hours = 0
  }

  const now = new Date()
  let year = now.getFullYear()
  let target = new Date(year, month, day, hours, minutes, 0)

  // If the parsed date is well in the past, assume it refers to next year
  if (target.getTime() < now.getTime() - 12 * 60 * 60 * 1000) {
    target = new Date(year + 1, month, day, hours, minutes, 0)
  }

  if (isNaN(target.getTime())) return null
  return target
}

function formatCountdown(target, now) {
  const diffMs = target.getTime() - now.getTime()
  if (diffMs <= 0) return null
  const totalMinutes = Math.floor(diffMs / 60000)
  const days = Math.floor(totalMinutes / 1440)
  const hrs = Math.floor((totalMinutes % 1440) / 60)
  const mins = totalMinutes % 60

  const parts = []
  if (days > 0) parts.push(`${days}d`)
  if (days > 0 || hrs > 0) parts.push(`${hrs}h`)
  parts.push(`${mins}m`)
  return parts.join(' ')
}

function extractDateLabel(text) {
  if (!text) return ''
  const m = text.match(/\bon\s+([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?(?:\s+at\s+\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?(?:\s*[A-Z]{2,4})?)?)/i)
  return m ? m[1].trim() : ''
}

function Countdown({ target }) {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    if (!target) return
    const id = setInterval(() => setNow(new Date()), 60000)
    return () => clearInterval(id)
  }, [target])

  if (!target) return null
  const label = formatCountdown(target, now)
  if (!label) return null

  return (
    <div className="w-countdown">
      <span className="w-countdown-dot"></span>
      Tips off in <strong>{label}</strong>
    </div>
  )
}

function formatScheduleTime(statusText) {
  if (!statusText) return ''
  const m = statusText.match(/(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?/i)
  if (!m) return statusText
  const mins = m[2] ? `:${m[2]}` : ''
  const meridiem = m[3].toUpperCase() + 'M'
  return `${m[1]}${mins} ${meridiem} ET`
}

function formatShortDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(`${dateStr}T00:00:00`)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function WatchNext({ watch_next, upcoming_games = [] }) {
  if (!watch_next && (!upcoming_games || upcoming_games.length === 0)) return null

  // e.g. "New York Knicks vs San Antonio Spurs on June 5 at 8:30 pm ET — reason..."
  const vsMatch = watch_next ? watch_next.match(/^([^—\n]+(?:vs\.?|@)[^—\n]+?)(?:\s+on\s+([^—]+?))?(?:\s*—\s*(.*))?$/i) : null

  let matchup = ''
  let date = ''
  let copy = ''

  if (vsMatch) {
    matchup = vsMatch[1].trim()
    date = vsMatch[2] ? vsMatch[2].trim() : ''
    const rawCopy = vsMatch[3] ? vsMatch[3].trim() : ''
    copy = rawCopy.charAt(0).toUpperCase() + rawCopy.slice(1)
  } else {
    copy = watch_next
  }

  // Make sure the date/time is always surfaced, even when the matchup
  // string doesn't follow the "X vs Y on <date>" shape.
  if (!date) date = extractDateLabel(watch_next)

  const gameTime = parseGameDateTime(watch_next)

  // Match the featured pick against the structured schedule so the header
  // can show reliable tricode/date/time info regardless of how Claude phrased it.
  const featuredGame = watch_next
    ? upcoming_games.find(g => {
        const wn = watch_next.toLowerCase()
        const mentionsTeam = (fullName, tricode) => {
          if (tricode && wn.includes(tricode.toLowerCase())) return true
          const nickname = (fullName || '').trim().split(/\s+/).pop().toLowerCase()
          return nickname.length > 2 && wn.includes(nickname)
        }
        return mentionsTeam(g.away_team, g.away_tricode) && mentionsTeam(g.home_team, g.home_tricode)
      })
    : null

  const restOfSchedule = upcoming_games.filter(g => g !== featuredGame)

  let gameLine = ''
  if (featuredGame) {
    const parts = [`${featuredGame.away_tricode} @ ${featuredGame.home_tricode}`]
    const shortDate = formatShortDate(featuredGame.scheduled_date)
    if (shortDate) parts.push(shortDate)
    const time = formatScheduleTime(featuredGame.game_status_text)
    if (time) parts.push(time)
    gameLine = parts.join(' · ')
  } else if (matchup) {
    const parts = [matchup.replace(/\s+(vs\.?|@)\s+/i, ' @ ')]
    if (date) parts.push(date)
    gameLine = parts.join(' · ')
  }

  return (
    <div className="watch">
      {watch_next && (
        <>
          <div className="w-eyebrow">Featured Pick</div>
          {gameLine && (
            <div className="w-featured-head">
              <div className="w-game-line">{gameLine}</div>
              <Countdown target={gameTime} />
            </div>
          )}
          {copy && <div className="w-copy">{copy}</div>}
        </>
      )}

      {restOfSchedule.length > 0 && (
        <>
          <div className="w-divider"></div>
          <div className="w-schedule">
            {restOfSchedule.map((g, i) => (
              <div className="w-row" key={i}>
                <span className="w-row-matchup">
                  {formatShortDate(g.scheduled_date)} · {g.away_tricode} @ {g.home_tricode}
                </span>
                <span className="w-row-meta">
                  {formatScheduleTime(g.game_status_text)}
                  {g.series_game_number ? `  ·  ${g.series_game_number}` : ''}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
