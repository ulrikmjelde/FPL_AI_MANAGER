import httpx


class XClient:
    def __init__(self, bearer_token: str):
        self.headers = {'Authorization': f'Bearer {bearer_token}'}
        self.base = 'https://api.x.com/2'

    async def user_id(self, username: str) -> str:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f'{self.base}/users/by/username/{username}', headers=self.headers)
            r.raise_for_status()
            return r.json()['data']['id']

    async def latest_posts(self, user_id: str, since_id: str | None = None) -> list[dict]:
        params = {
            'max_results': 10,
            'tweet.fields': 'created_at,entities,referenced_tweets',
            'exclude': 'retweets, replies',
        }
        if since_id:
            params['since_id'] = since_id
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f'{self.base}/users/{user_id}/tweets', headers=self.headers, params=params)
            r.raise_for_status()
            return r.json().get('data', [])
