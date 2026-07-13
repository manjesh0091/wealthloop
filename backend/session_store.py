"""In-memory session registry shared by the analyze/stream/approve routers.

Not persisted, not multi-process safe -- fine for a single-process hackathon
demo. Each session_id (== the graph's thread_id) maps to an asyncio.Queue of
SSE-ready event dicts plus a little bookkeeping so /api/approve can validate
that a session is actually paused before trying to resume it.
"""

import asyncio
from dataclasses import dataclass, field


@dataclass
class Session:
    queue: "asyncio.Queue[dict]" = field(default_factory=asyncio.Queue)
    awaiting_approval: bool = False
    done: bool = False


SESSIONS: dict[str, Session] = {}


def create_session(session_id: str) -> Session:
    session = Session()
    SESSIONS[session_id] = session
    return session


def get_session(session_id: str) -> Session | None:
    return SESSIONS.get(session_id)
