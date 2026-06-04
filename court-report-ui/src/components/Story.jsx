export default function Story({ story, kicker }) {
  if (!story) return null

  // First sentence becomes the headline, rest is body
  const sentenceEnd = story.search(/(?<=[.!?])\s+[A-Z]/)
  const headline = sentenceEnd !== -1 ? story.slice(0, sentenceEnd).trim() : story
  const body = sentenceEnd !== -1 ? story.slice(sentenceEnd).trim() : ''

  return (
    <div className="story">
      <div className="story-kicker">{kicker || 'Story of the Night'}</div>
      <h1 className="story-hed">{headline}</h1>
      {body && <p className="story-body">{body}</p>}
    </div>
  )
}
