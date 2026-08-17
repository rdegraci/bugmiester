"""Request/response shapes for the Bugmiester API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RoundStartResponse(BaseModel):
    round_id: str
    bugs_per_round: int
    index: int
    round_score: int
    round_possible: int


class NextBugRequest(BaseModel):
    round_id: str


class NextBugResponse(BaseModel):
    round_id: str
    index: int
    bugs_per_round: int
    snippet_id: str
    language: str
    code: str
    difficulty: str
    degraded: bool = False


class SubmitRequest(BaseModel):
    round_id: str
    snippet_id: str
    answer: str = Field(min_length=1)


class RoundSummary(BaseModel):
    round_score: int
    round_possible: int
    correct_count: int
    partial_count: int
    incorrect_count: int


class SubmitResponse(BaseModel):
    correct: bool
    partial: bool
    points_awarded: int
    points_possible: int
    round_score: int
    round_possible: int
    index: int
    bugs_per_round: int
    feedback: str
    expected_summary: str
    round_complete: bool
    summary: RoundSummary | None = None


class ReportSnippetRequest(BaseModel):
    round_id: str
    snippet_id: str
    reason: str
    note: str = ""


class ReportSnippetResponse(BaseModel):
    ok: bool = True


def model_dump(obj: BaseModel) -> dict[str, Any]:
    return obj.model_dump()
