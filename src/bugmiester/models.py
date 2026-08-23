"""Request/response shapes for the Bugmiester API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Keep in sync with answer textarea maxlength and prompt sanitizer.
MAX_PLAYER_ANSWER_CHARS = 1000


class RoundStartResponse(BaseModel):
    round_id: str
    bugs_per_round: int
    index: int
    round_score: int
    round_possible: int
    mix: str = "senior_mix"
    difficulty_label: str = ""


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
    mix: str = "senior_mix"
    difficulty_label: str = ""
    adaptation_hint: str = ""


class SubmitRequest(BaseModel):
    round_id: str
    snippet_id: str
    answer: str = Field(min_length=1, max_length=MAX_PLAYER_ANSWER_CHARS)


class RoundSummary(BaseModel):
    round_score: int
    round_possible: int
    correct_count: int
    partial_count: int
    incorrect_count: int


class RecoveryChoice(BaseModel):
    id: str
    text: str


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
    recovery_available: bool = False
    recovery_prompt: str = ""
    recovery_options: list[RecoveryChoice] = Field(default_factory=list)
    upgraded: bool = False


class RecoverRequest(BaseModel):
    round_id: str
    snippet_id: str
    option_id: str | None = None


class ReportSnippetRequest(BaseModel):
    round_id: str
    snippet_id: str
    reason: str
    note: str = ""


class ReportSnippetResponse(BaseModel):
    ok: bool = True


class RoundResumeResponse(BaseModel):
    """Current playable round view. No answer key until the snippet is scored."""

    round_id: str
    bugs_per_round: int
    round_score: int
    round_possible: int
    index: int
    round_complete: bool
    snippet_id: str | None = None
    language: str = "swift"
    code: str = ""
    difficulty: str = ""
    mix: str = "senior_mix"
    difficulty_label: str = ""
    adaptation_hint: str = ""
    degraded: bool = False
    answered: bool = False
    player_answer: str = ""
    correct: bool | None = None
    partial: bool | None = None
    points_awarded: int | None = None
    points_possible: int | None = None
    feedback: str = ""
    expected_summary: str = ""
    recovery_available: bool = False
    recovery_prompt: str = ""
    recovery_options: list[RecoveryChoice] = Field(default_factory=list)
    reported: bool = False
    summary: RoundSummary | None = None
    pending: NextBugResponse | None = None


def model_dump(obj: BaseModel) -> dict[str, Any]:
    return obj.model_dump()
