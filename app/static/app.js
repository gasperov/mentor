let currentTest = null;
let lastGeneratePayload = null;
let sessionId = createRuntimeId("sess");
let studentId = createRuntimeId("student");
let activeTopicKey = null;
let isBusy = false;

const generateForm = document.getElementById("generate-form");
const answersForm = document.getElementById("answers-form");
const testCard = document.getElementById("test-card");
const resultCard = document.getElementById("result-card");
const resultOutput = document.getElementById("result-output");
const regenerateBtn = document.getElementById("regenerate-btn");
const progressOutput = document.getElementById("progress-output");
const statusText = document.getElementById("status-text");

loadProgress();

generateForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (isBusy) return;
  resultCard.classList.add("hidden");

  const payload = {
    topic: document.getElementById("topic").value.trim(),
    chapter: document.getElementById("chapter").value.trim(),
    level: document.getElementById("level").value,
    language: "sl",
    question_count: Number(document.getElementById("question_count").value || 8),
  };

  const incomingKey = topicKey(payload);
  if (activeTopicKey && activeTopicKey !== incomingKey) {
    resetPracticeState();
  }
  activeTopicKey = incomingKey;
  lastGeneratePayload = payload;

  const btn = generateForm.querySelector("button[type='submit']");
  await withBusy(btn, "Generiranje...", "Generiraj test", async () => {
    setStatus("Generiram test...", "info");
    const res = await fetch("/api/tests/generate", {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const msg = await extractErrorMessage(res, "Napaka pri generiranju testa.");
      setStatus(msg, "error");
      return;
    }
    currentTest = await res.json();
    renderTest(currentTest);
    setStatus("Test je pripravljen.", "success");
  });
});

answersForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (isBusy || !currentTest) return;

  const answers = {};
  const formData = new FormData();
  currentTest.questions.forEach((q) => {
    if (q.type === "multiple_choice") {
      const checked = Array.from(document.querySelectorAll(`input[name="answer-${q.id}"]:checked`)).map(
        (el) => el.value
      );
      answers[q.id] = checked.join(" | ");
    } else {
      const el = document.getElementById(`answer-${q.id}`);
      answers[q.id] = el ? el.value.trim() : "";
    }

    const imageInput = document.getElementById(`image-${q.id}`);
    if (imageInput && imageInput.files && imageInput.files[0]) {
      formData.append(`image_${q.id}`, imageInput.files[0]);
    }
  });
  formData.append("test_id", currentTest.test_id);
  formData.append("answers_json", JSON.stringify(answers));

  const btn = answersForm.querySelector("button[type='submit']");
  await withBusy(btn, "Ocenjevanje...", "Oddaj in oceni", async () => {
    setStatus("Ocenjujem odgovore...", "info");
    const res = await fetch("/api/tests/grade", {
      method: "POST",
      headers: buildHeaders({ isMultipart: true }),
      body: formData,
    });
    if (!res.ok) {
      const msg = await extractErrorMessage(res, "Napaka pri ocenjevanju.");
      setStatus(msg, "error");
      return;
    }
    const grade = await res.json();
    renderResult(grade);
    await loadProgress();
    setStatus("Ocenjevanje uspesno zakljuceno.", "success");
  });
});

regenerateBtn.addEventListener("click", async () => {
  if (isBusy) return;
  if (!lastGeneratePayload) {
    setStatus("Najprej generiraj prvi test.", "error");
    return;
  }
  resultCard.classList.add("hidden");

  await withBusy(regenerateBtn, "Generiranje...", "Ustvari nov test brez ponovitev", async () => {
    setStatus("Generiram nov test brez ponovitev...", "info");
    const res = await fetch("/api/tests/generate", {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(lastGeneratePayload),
    });
    if (!res.ok) {
      const msg = await extractErrorMessage(res, "Napaka pri ponovni generaciji testa.");
      setStatus(msg, "error");
      return;
    }
    currentTest = await res.json();
    renderTest(currentTest);
    setStatus("Nov test je pripravljen.", "success");
  });
});

function renderTest(test) {
  answersForm.innerHTML = "";
  test.questions.forEach((q, idx) => {
    const wrap = document.createElement("div");
    wrap.className = "question";
    const typeText = q.type === "multiple_choice" ? "Izbirno vprasanje" : "Kratek odgovor";
    const optionsBlock =
      q.type === "multiple_choice" && Array.isArray(q.options)
        ? `<div>${q.options
            .map(
              (opt, i) => `
              <label>
                <input type="checkbox" name="answer-${q.id}" value="${escapeHtml(opt)}" />
                ${String.fromCharCode(65 + i)}. ${escapeHtml(opt)}
              </label>
            `
            )
            .join("")}</div>`
        : "";
    const answerInput =
      q.type === "multiple_choice"
        ? ""
        : `<textarea id="answer-${q.id}" placeholder="Vpisi odgovor..."></textarea>`;
    const imageInput = `
      <label for="image-${q.id}" class="mini">Dodaj sliko odgovora (telefon/kamera):</label>
      <input id="image-${q.id}" type="file" accept="image/*" capture="environment" />
    `;

    wrap.innerHTML = `
      <span class="pill">${typeText}</span>
      <div><strong>${idx + 1}. ${q.question}</strong></div>
      ${optionsBlock}
      ${answerInput}
      ${imageInput}
    `;
    answersForm.appendChild(wrap);
  });

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Oddaj in oceni";
  answersForm.appendChild(submit);

  testCard.classList.remove("hidden");
}

function renderResult(grade) {
  resultOutput.innerHTML = `
    <p class="score">${grade.total_score} / 100</p>
    <p><strong>Nivo znanja:</strong> ${grade.knowledge_level}</p>
    <p><strong>Povzetek:</strong> ${grade.summary_feedback}</p>
    <h3>Vrzeli znanja</h3>
    <ul>${grade.knowledge_gaps.map((x) => `<li>${x}</li>`).join("")}</ul>
    <h3>Poudarek za naslednji test</h3>
    <ul>${(grade.focus_areas_for_next_test || []).map((x) => `<li>${x}</li>`).join("")}</ul>
    <h3>Priporocila za ucenje</h3>
    <ul>${grade.learning_recommendations.map((x) => `<li>${x}</li>`).join("")}</ul>
    <h3>Po vprasanjih</h3>
    <ul>
      ${grade.per_question
        .map(
          (q) =>
            `<li><strong>${q.question_id}</strong>: ${q.score}/100 - ${q.feedback}${
              q.perfect_answer
                ? `<br/><span class="mini"><strong>Popoln odgovor (100%):</strong> ${escapeHtml(q.perfect_answer)}</span>`
                : ""
            }</li>`
        )
        .join("")}
    </ul>
  `;
  resultCard.classList.remove("hidden");
  resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function extractErrorMessage(response, fallback) {
  try {
    const data = await response.json();
    if (data && typeof data.detail === "string" && data.detail.trim().length > 0) {
      return data.detail;
    }
  } catch (_) {
    // Keep fallback
  }
  return fallback;
}

function buildHeaders(options = {}) {
  const headers = {
    "X-Session-Id": sessionId,
    "X-Student-Id": studentId,
  };
  if (!options.isMultipart) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

function createRuntimeId(prefix) {
  return `${prefix}-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

async function loadProgress() {
  const res = await fetch("/api/progress", {
    method: "GET",
    headers: buildHeaders(),
  });
  if (!res.ok) {
    progressOutput.innerHTML = "<p class='mini'>Napredek trenutno ni dosegljiv.</p>";
    return;
  }
  const data = await res.json();
  renderProgress(data);
}

function renderProgress(data) {
  if (!data.attempts || data.attempts.length === 0) {
    progressOutput.innerHTML = "<p class='mini'>Se ni zabelezenih rezultatov.</p>";
    return;
  }

  const latest = data.attempts.slice(-10).reverse();
  progressOutput.innerHTML = `
    <p><strong>Poskusov:</strong> ${data.summary.attempt_count}</p>
    <p><strong>Povprecje:</strong> ${data.summary.average_score}</p>
    <p><strong>Zadnji rezultat:</strong> ${data.summary.latest_score ?? "-"}</p>
    <h3>Zadnjih 10 poskusov</h3>
    <ul>
      ${latest
        .map(
          (a) =>
            `<li>${formatTimestamp(a.timestamp)} | ${a.topic} / ${a.chapter} | ${a.score}/100 | ${a.knowledge_level}</li>`
        )
        .join("")}
    </ul>
  `;
}

function formatTimestamp(ts) {
  try {
    return new Date(ts).toLocaleString("sl-SI");
  } catch (_) {
    return ts;
  }
}

function topicKey(payload) {
  return [payload.topic, payload.chapter, payload.level].join("|").toLowerCase();
}

function resetPracticeState() {
  sessionId = createRuntimeId("sess");
  studentId = createRuntimeId("student");
  currentTest = null;
  lastGeneratePayload = null;
  answersForm.innerHTML = "";
  resultOutput.innerHTML = "";
  testCard.classList.add("hidden");
  resultCard.classList.add("hidden");
  progressOutput.innerHTML = "<p class='mini'>Se ni zabelezenih rezultatov.</p>";
  setStatus("Nova tema zaznana. Stanje je resetirano.", "info");
}

function setStatus(message, kind) {
  statusText.textContent = message;
  statusText.classList.remove("info", "success", "error");
  statusText.classList.add(kind);
}

async function withBusy(button, busyText, normalText, fn) {
  isBusy = true;
  setUiBusy(true);
  const original = button ? button.textContent : normalText;
  if (button) {
    button.disabled = true;
    button.textContent = busyText;
  }
  try {
    await fn();
  } finally {
    if (button) {
      button.textContent = normalText || original || "";
      button.disabled = false;
    }
    isBusy = false;
    setUiBusy(false);
  }
}

function setUiBusy(state) {
  const genBtn = generateForm.querySelector("button[type='submit']");
  const gradeBtn = answersForm.querySelector("button[type='submit']");
  if (genBtn) genBtn.disabled = state;
  if (gradeBtn) gradeBtn.disabled = state;
  if (regenerateBtn) regenerateBtn.disabled = state;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
