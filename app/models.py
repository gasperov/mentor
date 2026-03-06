from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_TOPIC_CHARS = 2000
MAX_CHAPTER_CHARS = 2000
MAX_TEST_ID_CHARS = 128
MAX_QUESTION_ID_CHARS = 64
MAX_ANSWER_CHARS = 2000
MAX_ANSWER_ITEMS = 30


class SchoolLevel(str, Enum):
    basic = "osnovna"
    gymnasium_standard = "gimnazija_standard"
    gymnasium_advanced = "gimnazija_napredno"


class QuestionType(str, Enum):
    multiple_choice = "multiple_choice"
    short_answer = "short_answer"


class TestRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=MAX_TOPIC_CHARS)
    chapter: str = Field(min_length=1, max_length=MAX_CHAPTER_CHARS)
    level: SchoolLevel
    language: Literal["sl"] = "sl"
    question_count: int = Field(default=8, ge=3, le=30)

    @field_validator("topic", "chapter")
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        return value.strip()


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
    test_id: str = Field(min_length=1, max_length=MAX_TEST_ID_CHARS)
    answers: dict[str, str]

    @field_validator("test_id")
    @classmethod
    def strip_test_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > MAX_ANSWER_ITEMS:
            raise ValueError(f"Najvecje dovoljeno stevilo odgovorov je {MAX_ANSWER_ITEMS}.")

        normalized: dict[str, str] = {}
        for raw_key, raw_answer in value.items():
            key = str(raw_key).strip()
            answer = str(raw_answer).strip()
            if not key:
                raise ValueError("ID vprasanja ne sme biti prazen.")
            if len(key) > MAX_QUESTION_ID_CHARS:
                raise ValueError(f"ID vprasanja je predolg (max {MAX_QUESTION_ID_CHARS} znakov).")
            if len(answer) > MAX_ANSWER_CHARS:
                raise ValueError(f"Odgovor je predolg (max {MAX_ANSWER_CHARS} znakov).")
            normalized[key] = answer
        return normalized


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
