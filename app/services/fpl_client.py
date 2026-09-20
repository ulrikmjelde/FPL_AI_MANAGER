from __future__ import annotations
import httpx
from app.core.config import Settings
import os
from pathlib import Path

class FPLClient:
    BASE = 'https://fantasy.premierleague.com/api'

    def __init__(self, settings: Settings):
        self.s = settings
        self.access_token = self._normalize_token(settings.fpl_access_token)
        self.refresh_token = settings.fpl_refresh_token

    @staticmethod
    def _normalize_token(token: str) -> str:
        return token.removeprefix('Bearer ').strip()

    def _headers(self) -> dict[str, str]:
        return {
            'X-API-Authorization': f'Bearer {self.access_token}',
            'User-Agent': 'Mozilla/5.0 FPL-Shadow-Manager/0.1',
            'Accept': 'application/json',
            'Referer': 'https://fantasy.premierleague.com/',
        }

    async def refresh_access_token(self) -> bool:
        refresh_token = self._load_refresh_token()

        if not refresh_token:
            return False

        data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': self.s.fpl_oidc_client_id,
        }

        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(self.s.fpl_oidc_token_url, data=data)

            if r.status_code >= 400:
                return False

            payload = r.json()

            self.access_token = payload['access_token']

            new_refresh_token = payload.get(
                'refresh_token',
                refresh_token,
            )

            self._save_refresh_token(new_refresh_token)

        return True

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.request(method, f'{self.BASE}{path}', headers=self._headers(), **kwargs)
            if r.status_code in (401, 403) and await self.refresh_access_token():
                r = await c.request(method, f'{self.BASE}{path}', headers=self._headers(), **kwargs)
            r.raise_for_status()
            return r

    async def bootstrap(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f'{self.BASE}/bootstrap-static/', headers={'User-Agent': self._headers()['User-Agent']})
            r.raise_for_status()
            return r.json()

    async def fixtures(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f'{self.BASE}/fixtures/', headers={'User-Agent': self._headers()['User-Agent']})
            r.raise_for_status()
            return r.json()

    async def my_team(self) -> dict:
        return (await self._request('GET', f'/my-team/{self.s.fpl_entry_id}/')).json()

    async def latest_transfers(self) -> list[dict]:
        return (await self._request('GET', f'/entry/{self.s.fpl_entry_id}/transfers-latest/')).json()

    async def make_transfers(
        self,
        *,
        event: int,
        transfers: list[dict],
        chip: str | None = None,
    ) -> dict:
        payload = {
            "chip": chip,
            "entry": self.s.fpl_entry_id,
            "event": event,
            "transfers": transfers,
        }

        response = await self._request(
            "POST",
            "/transfers/",
            json=payload,
        )

        if not response.content:
            return {
                "ok": True,
                "status_code": response.status_code,
            }

        try:
            return response.json()
        except ValueError:
            return {
                "ok": True,
                "status_code": response.status_code,
                "text": response.text[:500],
            }

    def _load_refresh_token(self) -> str | None:
        if self.refresh_token_file:
            path = Path(self.refresh_token_file)
            if path.exists():
                token = path.read_text().strip()
                if token:
                    return token

        return self.refresh_token

    def _save_refresh_token(self, token: str) -> None:
        self.refresh_token = token

        if not self.refresh_token_file:
            return

        path = Path(self.refresh_token_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(token)
        os.chmod(tmp, 0o600)
        tmp.replace(path)

    path = Path(self.refresh_token_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(token)
    os.chmod(tmp, 0o600)
    tmp.replace(path)

def __init__():
    self.refresh_token_file = settings.fpl_refresh_token_file
