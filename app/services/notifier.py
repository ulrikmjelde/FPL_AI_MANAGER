import httpx


async def notify(url: str | None, message: str) -> None:
    if not url:
        return
    async with httpx.AsyncClient(timeout=15) as c:
        try:
            await c.post(url, json={'content': message, 'text': message})
        except Exception:
            pass
