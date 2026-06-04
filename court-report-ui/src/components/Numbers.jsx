function parseNumberCard(str) {
  // e.g. "28.6% FG: Victor Wembanyama — worst shooting performance..."
  const colonIdx = str.indexOf(':')
  if (colonIdx === -1) return { fig: str, who: '', ctx: '' }

  const fig = str.slice(0, colonIdx).trim()
  const rest = str.slice(colonIdx + 1).trim()

  const dashIdx = rest.indexOf('—')
  if (dashIdx === -1) return { fig, who: rest, ctx: '' }

  const who = rest.slice(0, dashIdx).trim()
  const raw = rest.slice(dashIdx + 1).trim()
  const ctx = raw.charAt(0).toUpperCase() + raw.slice(1)
  return { fig, who, ctx }
}

export default function Numbers({ by_the_numbers = [] }) {
  if (!by_the_numbers.length) return null

  return (
    <div className="numbers">
      <div className="rh">
        <span className="rh-label">By the Numbers</span>
        <div className="rh-line"></div>
      </div>
      <div className="num-grid">
        {by_the_numbers.map((item, i) => {
          const { fig, who, ctx } = parseNumberCard(item)
          return (
            <div className="num-card" key={i}>
              <div className="num-fig">{fig}</div>
              <div className="num-right">
                <div className="num-who">{who}</div>
                <div className="num-ctx">{ctx}</div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
