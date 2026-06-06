import { useState, useEffect } from 'react'
import Masthead from './components/Masthead'
import Ticker from './components/Ticker'
import Story from './components/Story'
import Players from './components/Players'
import Numbers from './components/Numbers'
import GameCard from './components/GameCard'
import WatchNext from './components/WatchNext'
import Chat from './components/Chat'

const API = 'http://localhost:8000'

export default function App() {
  const [digest, setDigest] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API}/digest`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setDigest)
      .catch(e => setError(e.message))
  }, [])

  if (error) {
    return (
      <>
        <Masthead />
        <div className="error-screen">
          <div className="error-text">Failed to load digest</div>
          <div style={{ fontFamily: 'Barlow Condensed', fontSize: 13, color: 'var(--muted)' }}>{error}</div>
        </div>
        <Chat />
      </>
    )
  }

  if (!digest) {
    return (
      <>
        <Masthead />
        <div className="loading-screen">
          <div className="loading-text">Generating your Court Report</div>
          <div className="loading-sub">Pulling box scores, player stats, and storylines from last night's games&hellip;</div>
          <div className="loading-bar"><div className="loading-bar-fill"></div></div>
        </div>
        <Chat />
      </>
    )
  }

  return (
    <>
      <Masthead date={digest.date} />
      <Ticker games={digest.games || []} />
      <div className="wrap">
        <Story story_headline={digest.story_headline} story_body={digest.story_body} kicker={`Story of the Night — ${digest.date || ''}`} />
        <Players players={digest.players || {}} games={digest.games || []} />
        <Numbers by_the_numbers={digest.by_the_numbers || []} />
        <div className="games">
          <div className="rh">
            <span className="rh-label">Game Recap</span>
            <div className="rh-line"></div>
          </div>
          {(digest.games || []).map((g, i) => (
            <GameCard key={i} game={g} />
          ))}
        </div>
        <div style={{ marginTop: 36 }}>
          <div className="rh">
            <span className="rh-label">Watch Next</span>
            <div className="rh-line"></div>
          </div>
          <WatchNext watch_next={digest.watch_next} upcoming_games={digest.upcoming_games || []} />
        </div>
      </div>
      <Chat />
    </>
  )
}
