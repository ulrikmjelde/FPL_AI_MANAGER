import re
from youtube_transcript_api import YouTubeTranscriptApi

YT_RE = re.compile(r'(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|live/))([A-Za-z0-9_-]{6,})')


def extract_video_id(text: str) -> str | None:
    m = YT_RE.search(text)
    return m.group(1) if m else None


def fetch_transcript(video_id: str) -> str | None:
    try:
        rows = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'no'])
        return '\n'.join(r['text'] for r in rows)
    except Exception:
        return None
