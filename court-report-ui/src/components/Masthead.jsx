export default function Masthead({ date }) {
  const formatted = date
    ? new Date(date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
    : ''

  return (
    <div className="masthead">
      <div className="mast-top">
        <div className="mast-meta">{formatted}</div>
        <div className="mast-meta">Powered by Claude AI</div>
      </div>
      <div className="mast-center">
        <div className="logo">COURT<span>REPORT</span></div>
      </div>
      <div className="mast-rule">
        <div className="mast-rule-line"></div>
        <div className="mast-rule-text">Last night's NBA, all in one place.</div>
        <div className="mast-rule-line"></div>
      </div>
    </div>
  )
}
