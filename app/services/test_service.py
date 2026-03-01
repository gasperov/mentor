from __future__ import annotations

import re
import random
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.models import (
    GeneratedTest,
    GradeRequest,
    GradeResult,
    ProgressAttempt,
    ProgressResponse,
    ProgressSummary,
    QuestionGrade,
    QuestionType,
    SchoolLevel,
    TestQuestion,
    TestRequest,
)
from app.services.openai_client import AIClient
from app.services.progress_store import ProgressStore


class TestService:
    def __init__(self, ai_client: AIClient, progress_store: ProgressStore) -> None:
        self._ai = ai_client
        self._progress_store = progress_store
        self._tests: dict[str, GeneratedTest] = {}
        self._session_test_ids: dict[str, list[str]] = defaultdict(list)
        self._session_seen_questions: dict[str, set[str]] = defaultdict(set)
        self._session_focus_areas: dict[str, list[str]] = defaultdict(list)

    def generate_test(self, req: TestRequest, session_id: str) -> GeneratedTest:
        seen = self._session_seen_questions[session_id]
        focus_areas = self._session_focus_areas[session_id]
        generated = self._generate_with_ai(req, seen, focus_areas) if self._ai.enabled else self._generate_mock(req, session_id)
        self._tests[generated.test_id] = generated
        self._session_test_ids[session_id].append(generated.test_id)
        self._remember_questions(session_id, generated.questions)
        return generated

    def grade_test(self, req: GradeRequest, session_id: str, student_id: str) -> GradeResult:
        test = self._tests.get(req.test_id)
        if not test:
            raise KeyError("Test ne obstaja.")
        result = self._grade_with_ai(test, req.answers) if self._ai.enabled else self._grade_mock(test, req.answers)
        self._update_focus_areas(session_id, result)
        self._save_attempt(student_id, test, result)
        return result

    def get_progress(self, student_id: str) -> ProgressResponse:
        raw_attempts = self._progress_store.get_attempts(student_id)
        attempts = [ProgressAttempt.model_validate(x) for x in raw_attempts]
        if not attempts:
            return ProgressResponse(
                summary=ProgressSummary(attempt_count=0, average_score=0.0, latest_score=None),
                attempts=[],
            )
        scores = [a.score for a in attempts]
        summary = ProgressSummary(
            attempt_count=len(attempts),
            average_score=round(sum(scores) / len(scores), 1),
            latest_score=scores[-1],
        )
        return ProgressResponse(summary=summary, attempts=attempts[-30:])

    def _generate_with_ai(
        self, req: TestRequest, seen_questions: set[str], focus_areas: list[str]
    ) -> GeneratedTest:
        system_prompt = (
            "Ti si strokovnjak za pripravo srednjesolskih testov v slovenscini. "
            "Vrni izkljucno veljaven JSON brez dodatnega besedila."
        )
        focus_block = (
            f"Poseben poudarek na teh vrzelih: {focus_areas}. "
            "Pripravi vec vprasanj na teh podrocjih (vsaj 40%). "
            if focus_areas
            else ""
        )
        variation_mode = random.choice(
            [
                "uporabi problemski pristop",
                "uporabi primerjalni pristop",
                "uporabi aplikativni pristop na realnih primerih",
            ]
        )
        nonce = random.randint(1000, 9999)
        banned = list(seen_questions)[-20:]
        user_prompt = (
            f"Pripravi test iz teme '{req.topic}', poglavje '{req.chapter}', nivo '{req.level.value}'. "
            f"Ustvari {req.question_count} vprasanj. "
            f"Variacija testa: {variation_mode}. Random seed marker: {nonce}. "
            f"Pravila zahtevnosti: {self._difficulty_rules(req.level)} "
            f"{focus_block}"
            "Nikoli ne daj namigov, vodilnih vprasanj ali delov odgovora. "
            "Ne uporabljaj fraz: 'namig', 'pomoc', 'spomni se'. "
            f"Ne ponavljaj teh prejsnjih vprasanj (po pomenu in formulaciji): {banned}. "
            "JSON format: {\"questions\":[{\"id\":\"q1\",\"type\":\"multiple_choice|short_answer\","
            "\"question\":\"...\",\"options\":[\"...\"]}]} . "
            "Za short_answer naj bo 'options' null ali izpuscen."
        )
        data = self._ai.ask_for_json(system_prompt, user_prompt)
        questions = self._normalize_questions(data.get("questions", []))
        questions = self._dedupe_questions(questions, seen_questions)
        if not questions:
            questions = self._mock_questions(req.question_count, req.topic, req.chapter, req.level, seen_questions)
        elif len(questions) < req.question_count:
            filler = self._mock_questions(
                req.question_count - len(questions), req.topic, req.chapter, req.level, seen_questions
            )
            questions.extend(filler)
        random.shuffle(questions)
        for idx, q in enumerate(questions, start=1):
            q.id = f"q{idx}"

        return GeneratedTest(
            test_id=str(uuid.uuid4()),
            topic=req.topic,
            chapter=req.chapter,
            level=req.level,
            language=req.language,
            questions=questions,
        )

    def _grade_with_ai(self, test: GeneratedTest, answers: dict[str, str]) -> GradeResult:
        system_prompt = (
            "Ti si ocenjevalec testov v slovenscini. "
            "Vrni izkljucno veljaven JSON brez dodatnega besedila."
        )
        questions_repr = [
            {"id": q.id, "type": q.type.value, "question": q.question, "options": q.options}
            for q in test.questions
        ]
        user_prompt = (
            "Ocenjuj odgovore dijaka. "
            f"Vprasanja: {questions_repr}. "
            f"Odgovori dijaka: {answers}. "
            "Vrni JSON format: "
            "{\"total_score\":0-100,\"knowledge_level\":\"zacetnik|dober|zelo_dober|odlicen\","
            "\"summary_feedback\":\"...\",\"knowledge_gaps\":[\"...\"],\"focus_areas_for_next_test\":[\"...\"],"
            "\"learning_recommendations\":[\"...\"],\"per_question\":["
            "{\"question_id\":\"q1\",\"score\":0-100,\"feedback\":\"...\","
            "\"expected_key_points\":[\"...\"],\"perfect_answer\":\"...\"}"
            "]}"
        )
        data = self._ai.ask_for_json(system_prompt, user_prompt)
        return self._normalize_grade_result(data, test)

    def _generate_mock(self, req: TestRequest, session_id: str) -> GeneratedTest:
        seen = self._session_seen_questions[session_id]
        return GeneratedTest(
            test_id=str(uuid.uuid4()),
            topic=req.topic,
            chapter=req.chapter,
            level=req.level,
            language=req.language,
            questions=self._mock_questions(req.question_count, req.topic, req.chapter, req.level, seen),
        )

    def _grade_mock(self, test: GeneratedTest, answers: dict[str, str]) -> GradeResult:
        per_question: list[QuestionGrade] = []
        earned = 0
        for q in test.questions:
            raw = answers.get(q.id, "").strip()
            score = 80 if len(raw) > 25 else 45 if len(raw) > 5 else 10
            earned += score
            per_question.append(
                QuestionGrade(
                    question_id=q.id,
                    score=score,
                    feedback="Odgovor je delno ustrezen. Dodaj vec kljucnih pojmov.",
                    expected_key_points=["definicija", "primer", "uporaba v nalogi"],
                    perfect_answer=(
                        "Popoln odgovor: jasna definicija, kratek primer in razlaga uporabe v ustreznem kontekstu."
                    ),
                )
            )

        total = round(earned / max(len(test.questions), 1))
        return GradeResult(
            total_score=total,
            knowledge_level=self._knowledge_level_from_score(total),
            summary_feedback="Osnove so vidne, a razlaga je ponekod prekratka.",
            knowledge_gaps=["Nejasni osnovni pojmi", "Premalo natancne razlage"],
            focus_areas_for_next_test=["definicije kljucnih pojmov", "uporaba znanja na primerih"],
            learning_recommendations=[
                f"Ponovi poglavje '{test.chapter}' s poudarkom na definicijah.",
                "Resi se 5 krajsih nalog z razlago postopka.",
            ],
            per_question=per_question,
        )

    def _normalize_questions(self, raw_questions: list[dict[str, Any]]) -> list[TestQuestion]:
        out: list[TestQuestion] = []
        for idx, rq in enumerate(raw_questions, start=1):
            qid = str(rq.get("id") or f"q{idx}")
            qtype_raw = str(rq.get("type") or "short_answer")
            qtype = QuestionType.multiple_choice if qtype_raw == "multiple_choice" else QuestionType.short_answer
            question = self._strip_hints(str(rq.get("question") or "").strip())
            if not question:
                continue
            options = rq.get("options")
            if qtype == QuestionType.multiple_choice and not isinstance(options, list):
                options = ["A", "B", "C", "D"]
            out.append(TestQuestion(id=qid, type=qtype, question=question, options=options))
        return out

    def _mock_questions(
        self,
        n: int,
        topic: str,
        chapter: str,
        level: SchoolLevel,
        seen_questions: set[str],
    ) -> list[TestQuestion]:
        questions: list[TestQuestion] = []
        i = 1
        seed = len(seen_questions) + 1
        while len(questions) < n:
            idx = seed + i - 1
            if level == SchoolLevel.gymnasium_advanced:
                angle = random.choice(["analizo", "primerjavo", "kriticno presojo", "uporabo modela"])
                candidate = TestQuestion(
                    id=f"q{i}",
                    type=QuestionType.short_answer,
                    question=(
                        f"[{topic}/{chapter}] Pripravi {angle} za trditev #{idx} in primerjaj dva razlicna pristopa. "
                        "Vkljuci omejitve in posledice."
                    ),
                )
            elif i % 3 == 0:
                options = ["Moznost A", "Moznost B", "Moznost C", "Moznost D"]
                random.shuffle(options)
                candidate = TestQuestion(
                    id=f"q{i}",
                    type=QuestionType.multiple_choice,
                    question=f"[{topic}/{chapter}] Izberi pravilno trditev #{idx}.",
                    options=options,
                )
            else:
                verbs = ["razlozi", "opisi", "utemelji", "ponazori"]
                verb = random.choice(verbs)
                candidate = TestQuestion(
                    id=f"q{i}",
                    type=QuestionType.short_answer,
                    question=f"[{topic}/{chapter}] Na kratko {verb} pojem #{idx}.",
                )

            key = self._question_key(candidate.question)
            if key not in seen_questions:
                questions.append(candidate)
                seen_questions.add(key)
            i += 1
        return questions

    def _difficulty_rules(self, level: SchoolLevel) -> str:
        if level == SchoolLevel.gymnasium_advanced:
            return (
                "Napredno: vsaj 70% odprtih vprasanj; analiza, sinteza, argumentacija in prenos znanja "
                "na nov primer; brez direktnih definicij kot samostojnih vprasanj."
            )
        if level == SchoolLevel.gymnasium_standard:
            return "Standard: uravnotezi razumevanje pojmov in uporabo na primerih."
        return "Osnovna: preveri temeljno razumevanje in preprosto uporabo znanja."

    def _strip_hints(self, text: str) -> str:
        cleaned = re.sub(r"\((?:namig|pomoc|hint)[^)]*\)", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(?:namig|pomoc|hint)\b[:\-]?\s*.*$", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _question_key(self, text: str) -> str:
        compact = re.sub(r"[^a-z0-9]+", " ", text.lower())
        compact = re.sub(r"\s+", " ", compact).strip()
        return compact

    def _dedupe_questions(self, questions: list[TestQuestion], seen_questions: set[str]) -> list[TestQuestion]:
        unique: list[TestQuestion] = []
        local_seen: set[str] = set()
        for q in questions:
            key = self._question_key(q.question)
            if key in seen_questions or key in local_seen:
                continue
            local_seen.add(key)
            unique.append(q)
        for idx, q in enumerate(unique, start=1):
            q.id = f"q{idx}"
        return unique

    def _remember_questions(self, session_id: str, questions: list[TestQuestion]) -> None:
        seen = self._session_seen_questions[session_id]
        for q in questions:
            seen.add(self._question_key(q.question))

    def _knowledge_level_from_score(self, score: int) -> str:
        if score >= 90:
            return "odlicen"
        if score >= 75:
            return "zelo_dober"
        if score >= 60:
            return "dober"
        return "zacetnik"

    def _update_focus_areas(self, session_id: str, result: GradeResult) -> None:
        merged = [x.strip() for x in (result.focus_areas_for_next_test + result.knowledge_gaps) if x.strip()]
        unique: list[str] = []
        seen: set[str] = set()
        for item in merged:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        self._session_focus_areas[session_id] = unique[:8]

    def _normalize_grade_result(self, data: dict[str, Any], test: GeneratedTest) -> GradeResult:
        total = int(data.get("total_score", 0))
        total = max(0, min(100, total))
        level = str(data.get("knowledge_level") or self._knowledge_level_from_score(total))
        per_q_raw = data.get("per_question") or []
        per_question: list[QuestionGrade] = []
        for idx, q in enumerate(test.questions):
            found = next((x for x in per_q_raw if str(x.get("question_id")) == q.id), None)
            if found:
                per_question.append(
                    QuestionGrade(
                        question_id=q.id,
                        score=max(0, min(100, int(found.get("score", 0)))),
                        feedback=str(found.get("feedback") or "Brez komentarja."),
                        expected_key_points=list(found.get("expected_key_points") or []),
                        perfect_answer=str(found.get("perfect_answer") or ""),
                    )
                )
            else:
                per_question.append(
                    QuestionGrade(
                        question_id=q.id,
                        score=0,
                        feedback="Manjka ocena za to vprasanje.",
                        expected_key_points=[],
                        perfect_answer="",
                    )
                )

        return GradeResult(
            total_score=total,
            knowledge_level=level,
            summary_feedback=str(data.get("summary_feedback") or "Povzetek ni na voljo."),
            knowledge_gaps=list(data.get("knowledge_gaps") or []),
            focus_areas_for_next_test=list(data.get("focus_areas_for_next_test") or []),
            learning_recommendations=list(data.get("learning_recommendations") or []),
            per_question=per_question,
        )

    def _save_attempt(self, student_id: str, test: GeneratedTest, result: GradeResult) -> None:
        payload = ProgressAttempt(
            timestamp=datetime.now(timezone.utc).isoformat(),
            topic=test.topic,
            chapter=test.chapter,
            level=test.level,
            score=result.total_score,
            knowledge_level=result.knowledge_level,
            knowledge_gaps=result.knowledge_gaps[:5],
        ).model_dump()
        self._progress_store.append_attempt(student_id=student_id, payload=payload)
