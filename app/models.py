from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SchoolLevel(str, Enum):
    basic = "osnovna"
    gymnasium_standard = "gimnazija_standard"
    gymnasium_advanced = "gimnazija_napredno"


class QuestionType(str, Enum):
    multiple_choice = "multiple_choice"
    short_answer = "short_answer"


class TestRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=120)
    chapter: str = Field(min_length=1, max_length=120)
    level: SchoolLevel
    language: Literal["sl"] = "sl"
    question_count: int = Field(default=8, ge=3, le=20)


class TestQuestion(BaseModel):
    id: str
    type: QuestionType
    question: str
    options: list[str] | None = None


class GeneratedTest(BaseModel):
    test_id: str
    topic: str
    chapter: str
    level: SchoolLevel
    language: Literal["sl"] = "sl"
    questions: list[TestQuestion]


class GradeRequest(BaseModel):
    test_id: str
    answers: dict[str, str]


class QuestionGrade(BaseModel):
    question_id: str
    score: int = Field(ge=0, le=100)
    feedback: str
    expected_key_points: list[str] = Field(default_factory=list)
    perfect_answer: str = ""


class GradeResult(BaseModel):
    total_score: int = Field(ge=0, le=100)
    knowledge_level: str
    summary_feedback: str
    knowledge_gaps: list[str]
    focus_areas_for_next_test: list[str]
    learning_recommendations: list[str]
    per_question: list[QuestionGrade]


class ProgressAttempt(BaseModel):
    timestamp: str
    topic: str
    chapter: str
    level: SchoolLevel
    score: int = Field(ge=0, le=100)
    knowledge_level: str
    knowledge_gaps: list[str] = Field(default_factory=list)


class ProgressSummary(BaseModel):
    attempt_count: int
    average_score: float
    latest_score: int | None = None


class ProgressResponse(BaseModel):
    summary: ProgressSummary
    attempts: list[ProgressAttempt]
