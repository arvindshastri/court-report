export default function Story({ story_headline, story_body, kicker }) {
  if (!story_headline) return null

  return (
    <div className="story">
      <div className="story-kicker">{kicker || 'Story of the Night'}</div>
      <h1 className="story-hed">{story_headline}</h1>
      {story_body && <p className="story-body">{story_body}</p>}
    </div>
  )
}
