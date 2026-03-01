# Project TODO (MVP -> V1)

## 1. Core architecture (MVP)
- [ ] Chosen technology: Python + FastAPI + simple HTML/CSS/JS frontend.
- [ ] Define models: subject/topic/chapter/level, test, question, answer, grade, gaps.
- [ ] Add API endpoint for test generation via ChatGPT.
- [ ] Add API endpoint for answer grading and gap analysis.
- [ ] Keep tests in memory for now; migrate to a database later.

## 2. Prompting and content quality
- [ ] Prepare system prompts in Slovene for:
- [ ] generating questions by high school level,
- [ ] grading short and long-form answers,
- [ ] detecting gaps and suggesting learning actions.
- [ ] Enforce structured JSON output and validation.
- [ ] Add safeguards for invalid/incomplete model responses.

## 3. User flow (web)
- [ ] Page 1: enter topic/chapter/level.
- [ ] Page 2: solve the test.
- [ ] Page 3: result, points, mistake explanations, knowledge gaps.
- [ ] Add recommended next learning steps display (in Slovene).

## 4. Learning materials
- [ ] Endpoint for generating a short study plan based on gaps.
- [ ] Generate content summary, mini explanations, and extra exercises.
- [ ] Option to export a study sheet (PDF or Markdown).

## 5. Security and costs
- [ ] API key only via environment variable.
- [ ] Input length limits (topic/chapter) and basic rate limiting.
- [ ] Logging without personal data.
- [ ] Add budget guardrails (e.g., max number of questions / max tokens).

## 6. Testing and quality
- [ ] Unit tests for model validation and AI output parsing.
- [ ] Integration tests for API flow (generate -> answer -> grade).
- [ ] Edge-case tests (empty answers, very short answers, invalid JSON).

## 7. Production readiness
- [ ] Persistence (PostgreSQL) for test history.
- [ ] Authentication (students/teachers) and basic administration.
- [ ] Docker + CI pipeline.
- [ ] Monitoring (errors, latency, API usage).
