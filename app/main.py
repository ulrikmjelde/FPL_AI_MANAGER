import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import get_settings
from app.db.session import init_db
from app.services.fpl_client import FPLClient
from app.workers.monitor import Monitor

settings = get_settings()
monitor = Monitor(settings)
scheduler = AsyncIOScheduler()
lock = asyncio.Lock()


async def guarded_run():
    if lock.locked():
        return {'skipped': 'previous run still active'}
    async with lock:
        return await monitor.run_once()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.add_job(guarded_run, 'interval', seconds=settings.poll_seconds, max_instances=1, coalesce=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title='FPL Shadow Manager', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health():
    return {'ok': True, 'auto_transfer': settings.auto_transfer, 'creator': settings.x_creator_username}


@app.post('/run-now')
async def run_now():
    try:
        return await guarded_run()
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get('/fpl/check')
async def fpl_check():
    try:
        team = await FPLClient(settings).my_team()
        return {'ok': True, 'picks': len(team.get('picks', [])), 'bank': team.get('transfers', {}).get('bank')}
    except Exception as exc:
        raise HTTPException(500, f'FPL auth/API check failed: {exc}') from exc
