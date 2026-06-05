export default function WatchNext({ watch_next }) {
  if (!watch_next) return null

  // e.g. "New York Knicks vs San Antonio Spurs on June 5 at 8:30 pm ET — reason..."
  const vsMatch = watch_next.match(/^([^—\n]+(?:vs\.?|@)[^—\n]+?)(?:\s+on\s+([^—]+?))?(?:\s*—\s*(.*))?$/i)

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

  return (
    <div className="watch">
      {matchup && (
        <div className="w-matchup">
          {matchup.replace(/\s+(vs\.?|@)\s+/i, ' vs. ')}
        </div>
      )}
      {date && <div className="w-date">{date}</div>}
      {copy && <div className="w-copy">{copy}</div>}
    </div>
  )
}
