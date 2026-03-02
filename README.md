# LearnMe (MVP Scaffold)

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
Set these in `.env`:
- `SSL_CERTFILE=certs/server.crt`
- `SSL_KEYFILE=certs/server.key`

4. Configure Basic Auth users:
```bash
copy config\basic_auth_users.example.json config\basic_auth_users.json
```
Then edit `config/basic_auth_users.json` and set real credentials.
Example format:
```json
{
  "users": [
    { "username": "teacher", "password": "change-this-password" }
  ]
}
```

5. Start the HTTPS server:
```bash
python -m app.main
```

6. Open:
- `https://127.0.0.1:8443`
- API docs: `https://127.0.0.1:8443/docs`

## Current API
- `POST /api/tests/generate`
- `POST /api/tests/grade`
- `GET /api/progress`

All routes are protected with HTTP Basic Auth when `BASIC_AUTH_ENABLED=true`.
Example API call with Basic Auth:
```bash
curl -k -u teacher:change-this-password https://127.0.0.1:8443/api/progress
```

`POST /api/tests/grade` supports:
- JSON (`test_id`, `answers`) or
- `multipart/form-data` (`test_id`, `answers_json`, `image_<question_id>` files).

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
- Student identity is an anonymous `X-Student-Id` from `localStorage`.
- This allows progress history to persist across browser restarts.

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
