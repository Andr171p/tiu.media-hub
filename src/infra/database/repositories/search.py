from typing import Any

from uuid import UUID

from sqlalchemy import Float, cast, column, false, func, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.processing.ports import Transcript, TranscriptSegment
from src.application.processing.repositories import TranscriptRepository
from src.application.search.ports import SearchScope, TextHit, TextSearchRepository

from ..codec import from_json, to_json
from ..models import AssetOrm, TranscriptOrm

_HEADLINE_OPTIONS = "MaxWords=18, MinWords=6, ShortWord=2, StartSel=«, StopSel=»"


class SqlAlchemyTranscriptRepository(TranscriptRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, version_id: UUID, transcript: Transcript) -> None:
        values = {
            "language": transcript.language,
            "segments": to_json(list[TranscriptSegment], transcript.segments),
            "text": transcript.text,
        }
        stmt = (
            insert(TranscriptOrm)
            .values(version_id=version_id, **values)
            .on_conflict_do_update(index_elements=[TranscriptOrm.version_id], set_=values)
        )
        await self._session.execute(stmt)

    async def get(self, version_id: UUID) -> Transcript | None:
        model = await self._session.get(TranscriptOrm, version_id)
        if model is None:
            return None

        return Transcript(
            language=model.language, segments=from_json(list[TranscriptSegment], model.segments)
        )


class SqlAlchemyTextSearchRepository(TextSearchRepository):
    """Полнотекстовый поиск PostgreSQL: описание актива и речь текущей версии."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _scope(scope: SearchScope) -> list[Any]:
        conditions: list[Any] = [AssetOrm.deleted_at.is_(None)]

        if scope.collection_ids is not None:
            conditions.append(
                AssetOrm.collection_id.in_(scope.collection_ids) if scope.collection_ids else false()
            )
        if scope.kinds:
            conditions.append(AssetOrm.kind.in_([kind.value for kind in scope.kinds]))

        return conditions

    async def search(self, query: str, scope: SearchScope, *, limit: int) -> list[TextHit]:
        tsquery = func.websearch_to_tsquery("russian", query)

        rank = func.ts_rank(AssetOrm.search_vector, tsquery)
        assets_stmt = (
            select(AssetOrm.id, rank)
            .where(AssetOrm.search_vector.op("@@")(tsquery), *self._scope(scope))
            .order_by(rank.desc())
            .limit(limit)
        )

        segment = (
            func.jsonb_array_elements(TranscriptOrm.segments).table_valued(column("value", JSONB)).lateral()
        )
        first_moment = (
            select(cast(segment.c.value["start"].astext, Float))
            .where(func.to_tsvector("russian", segment.c.value["text"].astext).op("@@")(tsquery))
            .limit(1)
            .scalar_subquery()
        )
        speech_rank = func.ts_rank(TranscriptOrm.search_vector, tsquery)
        speech_stmt = (
            select(
                AssetOrm.id,
                speech_rank,
                func.ts_headline("russian", TranscriptOrm.text, tsquery, _HEADLINE_OPTIONS),
                first_moment,
            )
            .join(AssetOrm, AssetOrm.current_version_id == TranscriptOrm.version_id)
            .where(TranscriptOrm.search_vector.op("@@")(tsquery), *self._scope(scope))
            .order_by(speech_rank.desc())
            .limit(limit)
        )

        hits = [
            TextHit(asset_id=asset_id, rank=value)
            for asset_id, value in await self._session.execute(assets_stmt)
        ]
        hits.extend(
            TextHit(asset_id=asset_id, rank=value, snippet=snippet, timecode=moment)
            for asset_id, value, snippet, moment in await self._session.execute(speech_stmt)
        )
        return sorted(hits, key=lambda hit: hit.rank, reverse=True)


__all__ = ["SqlAlchemyTextSearchRepository", "SqlAlchemyTranscriptRepository"]
