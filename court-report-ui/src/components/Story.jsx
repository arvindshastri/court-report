import { useRef, useState } from 'react'

const API = 'http://localhost:8000'

export default function Story({ story_headline, story_body, kicker }) {
  const [status, setStatus] = useState('idle') // idle | loading | playing | unavailable
  const audioRef = useRef(null)

  if (!story_headline) return null

  const handleClick = async () => {
    if (status === 'unavailable') return

    if (status === 'playing') {
      audioRef.current?.pause()
      audioRef.current = null
      setStatus('idle')
      return
    }

    setStatus('loading')
    try {
      const res = await fetch(`${API}/api/digest/audio`, { method: 'POST' })
      if (!res.ok) throw new Error('TTS request failed')
      const blob = await res.blob()
      const audio = new Audio(URL.createObjectURL(blob))
      audioRef.current = audio
      audio.onended = () => setStatus('idle')
      await audio.play()
      setStatus('playing')
    } catch {
      setStatus('unavailable')
    }
  }

  return (
    <div className="story">
      <div className="story-kicker">{kicker || 'Story of the Night'}</div>
      <h1 className="story-hed">
        {story_headline}
        <button
          className={`tts-btn tts-btn-${status}`}
          onClick={handleClick}
          disabled={status === 'unavailable' || status === 'loading'}
          title={status === 'unavailable' ? 'TTS unavailable' : 'Read headline aloud'}
          aria-label="Read headline aloud"
        >
          {status === 'loading' ? (
            <span className="tts-spinner" />
          ) : status === 'playing' ? (
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <rect x="6" y="5" width="4" height="14" />
              <rect x="14" y="5" width="4" height="14" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M3 9v6h4l5 5V4L7 9H3z" />
              <path d="M16.5 12c0-1.77-1-3.29-2.5-4.03v8.06c1.5-.74 2.5-2.26 2.5-4.03z" />
            </svg>
          )}
        </button>
      </h1>
      {story_body && <p className="story-body">{story_body}</p>}
    </div>
  )
}
