from dataclasses import dataclass, field
from typing import Protocol

from app.domain.personalization.schemas import SearchProfileRead
from app.domain.search.schemas import CandidateItem, CurrentActor


@dataclass(slots=True)
class RankingQueryContext:
    original: str
    normalized: str
    corrected: str | None
    applied_synonyms: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RankingRequest:
    query: RankingQueryContext
    actor: CurrentActor
    profile: SearchProfileRead
    candidates: list[CandidateItem] = field(default_factory=list)


class RankingProvider(Protocol):
    def rank(self, request: RankingRequest) -> list[CandidateItem]:
        """Rank candidates without exposing ML internals to the backend."""


class NoopRankingProvider:
    def rank(self, request: RankingRequest) -> list[CandidateItem]:
        return sorted(request.candidates, key=lambda item: item.score, reverse=True)
