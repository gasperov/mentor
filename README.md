# OceniMe (MVP Scaffold)

Web app for:
- generating tests by subject/chapter/level,
- solving tests in the browser,
- grading answers and identifying knowledge gaps,
- all in Slovene.

## Why Python (and not Go)?
- faster MVP iteration for AI workflows (prompting + JSON validation),
- more mature ecosystem for LLM integrations,
- FastAPI enables a quick path from prototype to production.

## Run
1. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
copy .env.example .env
```
Set `OPENAI_API_KEY` in `.env`.
The default model is `gpt-5` (higher quality). If that model is not available for your account, the app automatically falls back to `gpt-4.1`.

3. Configure HTTPS certificate and key paths (self-signed is fine for local/dev):
```bash
mkdir certs
```
Generate a local TLS certificate pair (OpenSSL):
```bash
openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes -keyout certs/server.key -out certs/server.crt -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```
If OpenSSL is not available on Windows, use `mkcert`:
```bash
mkcert -install
mkcert -cert-file certs/server.crt -key-file certs/server.key localhost 127.0.0.1
```
Set these in `.env`:
- `SSL_CERTFILE=certs/server.crt`
- `SSL_KEYFILE=certs/server.key`
Note: SSH keys generated with `ssh-keygen` cannot be used as HTTPS TLS certs.

4. Start the HTTPS server:
```bash
python -m app.main
```

5. Open:
- `https://127.0.0.1:8443`
- API docs: `https://127.0.0.1:8443/docs`

## Linux detached run (SSH-safe)
Use this when deploying on a Linux server and you want the app to keep running after SSH disconnect.

1. Make script executable:
```bash
chmod +x scripts/linux_run_detached.sh
```

2. Start in background (creates venv, installs deps, runs app):
```bash
./scripts/linux_run_detached.sh start
```

3. Check status/logs:
```bash
./scripts/linux_run_detached.sh status
./scripts/linux_run_detached.sh logs
```

4. Stop server:
```bash
./scripts/linux_run_detached.sh stop
```

## Current API
- `POST /api/tests/generate`
- `POST /api/tests/grade`
- `GET /api/progress`

`POST /api/tests/grade` supports:
- JSON (`test_id`, `answers`) or
- `multipart/form-data` (`test_id`, `answers_json`, `image_<question_id>` files).

Rate limits:
- `POST /api/tests/generate`: max 1 call per 60 seconds per session (`X-Session-Id`).
- `POST /api/tests/grade`: max 1 call per 60 seconds per session (`X-Session-Id`).
- If the limit is exceeded, API returns `429` with `Retry-After` header.
- `POST /api/tests/generate` and `POST /api/tests/grade` additionally require a UI security token (cookie + `X-UI-Token` header match), which helps block crawler/bot direct calls.

Grading safety:
- A given `test_id` can be graded only once.
- Re-grading an already graded test returns `409`.

If `OPENAI_API_KEY` is not set, the app uses mock mode (so the frontend flow works immediately).

## Adaptive repetition
- The frontend uses a runtime `X-Session-Id` (only while the page is open).
- Within a session, the system:
- does not repeat previous questions,
- saves knowledge gaps after grading and emphasizes them in the next test.
- On reload or tab/browser close, the session is forgotten (fresh start).
- Changing subject/chapter/level automatically resets the session to avoid state mixing across topics.

## Progress storage
- Progress (attempt results) is saved to `data/progress.json`.
- An additional tabular grading log is saved to `data/progress.txt`.
- Each graded attempt now also stores `client_ip` in both files.
- Student identity is an anonymous `X-Student-Id` from `localStorage`.
- This allows progress history to persist across browser restarts.

## API audit logs
- API event audit log (JSONL) is saved to `data/api_events.jsonl`.
- Tabular API event log is saved to `data/api_events.txt`.
- Each event includes timestamp, endpoint, status, client IP, session ID, student ID, and request context (`topic/chapter/test_id` when available).

## Themes Database
- Themes DB file: `data/themes_database.json`.
- Regenerate with:
```bash
python scripts/regenerate_themes_db.py
```
- Fallback mode (no network):
```bash
python scripts/regenerate_themes_db.py --no-fetch
```
- Official-only bucket (store only discovered official themes in `themes.official_all`):
```bash
python scripts/regenerate_themes_db.py --official-only
```
- The file stores source URLs and any fetch errors under `source_urls` and `fetch_errors`.
- Exhaustive discovered candidates are stored under `themes_official_all`:
  - `themes_official_all.by_source`
  - `themes_official_all.all`

## Test randomness
- Generation uses a variation marker and randomized approach, so new tests are not always identical.
- Similar questions are allowed, but exact repeats within a session are blocked.

## Image answers (phone)
- You can add an image answer to each question.
- The app now shows a QR code with the current connect URL, so you can open the app quickly on your phone.
- On mobile, you now get explicit actions for `Open camera` and `Choose from gallery`.
- A preview and filename are shown before submit, and you can remove a selected image.
- If no image is attached, grading uses JSON; if at least one image is attached, grading uses `multipart/form-data`.
- Attached images are sent with answers and marked as labeled image answers for each question.

## AI model indicator
- The UI shows the currently used AI model after test generation/grading.
- If fallback happens (for example from `gpt-5` to `gpt-4.1`), the indicator explicitly shows both models.

## Grading
- For each question, the result now also includes `Perfect answer (100%)`, showing an example ideal answer.
- Grading prompt is stricter and emphasizes factual correctness and consistent scoring.
- Final `total_score` is normalized from per-question scores for consistent grading output.

## Prevent computer sleep
- On Windows, while the backend process is running, the app requests that the system does not sleep.
- When you stop the backend, that setting is automatically released.

## Suggested next iteration
- persistence (PostgreSQL),
- better prompts + stricter JSON schema,
- separate endpoint for generating study material from knowledge gaps,
- user authorization (student/teacher).

## License
This project is licensed under the MIT License. See the `LICENSE` file.
