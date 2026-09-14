import asyncio
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from analysis.jobs import MAX_ANALYZE_GAMES
from analysis.pipeline import process_game
from analysis.stockfish_worker import load_fen_cache_from_db, stockfish_pool
from db.database import SessionLocal
from db.models import Game
from ingestion.pipeline import ingest_user_games
from profiler.clusterer import refresh_weakness_profile

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def get_tracked_usernames() -> list[str]:
    """Usernames to refresh nightly, from TRACKED_USERNAMES only.

    This used to fall back to every username in the database, which meant any
    account someone once typed in (including very active ones) got a full,
    uncapped re-analysis every night on the same instance that serves the API.
    That starved the health check at 02:00 UTC and got the service restarted.
    The refresh is now opt-in: no list, no nightly work.
    """
    raw = os.getenv("TRACKED_USERNAMES", "").strip()
    return [name.strip().lower() for name in raw.split(",") if name.strip()]


@scheduler.scheduled_job("cron", hour=2)  # 02:00 in the container's timezone (UTC on Render)
async def nightly_update():
    """For each tracked user: fetch new games, analyze them, rebuild the profile.

    Bounded by the same MAX_ANALYZE_GAMES cap as user-triggered runs so a busy
    account can't turn this into hours of Stockfish on the web instance.
    """
    usernames = get_tracked_usernames()
    if not usernames:
        return

    cap = MAX_ANALYZE_GAMES or None
    for username in usernames:
        db = SessionLocal()
        try:
            ingested_ids = await ingest_user_games(username, db, max_new_games=cap)

            query = (
                db.query(Game)
                .filter_by(username=username, analyzed=False)
                .order_by(Game.played_at.desc())
            )
            game_ids = [g.id for g in (query.limit(cap) if cap else query).all()]

            analyzed = 0
            if game_ids:
                fen_cache = load_fen_cache_from_db(db, username)
                engine = await stockfish_pool.get_engine()
                for game_id in game_ids:
                    if await process_game(game_id, db, fen_cache, engine):
                        analyzed += 1
                    # Let pending requests (including the platform health check)
                    # run between games instead of queueing behind the whole batch.
                    await asyncio.sleep(0)

            if ingested_ids or analyzed:
                profiles = refresh_weakness_profile(username, db)
                logger.info(
                    "Nightly [%s]: ingested %d, analyzed %d, %d weakness themes",
                    username, len(ingested_ids), analyzed, len(profiles),
                )
        except Exception:
            db.rollback()
            logger.exception("Nightly update failed for %s", username)
        finally:
            db.close()


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
