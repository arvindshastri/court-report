export default function Masthead({ date }) {
  const formatted = date
    ? new Date(date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
    : ''

  return (
    <div className="masthead">
      <div className="mast-center">
        <div className="logo">COURT<span>REPORT</span></div>
      </div>
      <div className="mast-rule">
        <div className="mast-rule-line"></div>
        <div className="mast-rule-text">Last night's NBA, all in one place.</div>
        <div className="mast-rule-line"></div>
      </div>
      <div className="mast-byline">
        {formatted && <span>{formatted}</span>}
        {formatted && <span className="mast-byline-sep">·</span>}
        <span>Powered by Claude AI</span>
      </div>
    </div>
  )
}
