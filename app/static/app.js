let currentTest = null;
let lastGeneratePayload = null;
let sessionId = createRuntimeId("sess");
let studentId = createRuntimeId("student");
let activeTopicKey = null;
let isBusy = false;
const selectedImages = new Map();
const previewUrls = new Map();

const generateForm = document.getElementById("generate-form");
const answersForm = document.getElementById("answers-form");
const testCard = document.getElementById("test-card");
const resultCard = document.getElementById("result-card");
const resultOutput = document.getElementById("result-output");
const regenerateBtn = document.getElementById("regenerate-btn");
const progressOutput = document.getElementById("progress-output");
const statusText = document.getElementById("status-text");
const modelIndicator = document.getElementById("model-indicator");

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
    updateModelIndicatorFromResponse(res);
    currentTest = await res.json();
    renderTest(currentTest);
    setStatus("Test je pripravljen.", "success");
  });
});

answersForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (isBusy || !currentTest) return;

  const answers = {};
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
  });
  const hasImages = selectedImages.size > 0;

  const btn = answersForm.querySelector("button[type='submit']");
  await withBusy(btn, "Ocenjevanje...", "Oddaj in oceni", async () => {
    setStatus(hasImages ? "Ocenjujem odgovore in nalagam slike..." : "Ocenjujem odgovore...", "info");
    let body;
    let headers;

    if (hasImages) {
      const formData = new FormData();
      currentTest.questions.forEach((q) => {
        const file = selectedImages.get(String(q.id));
        if (file) {
          formData.append(`image_${q.id}`, file);
        }
      });
      formData.append("test_id", currentTest.test_id);
      formData.append("answers_json", JSON.stringify(answers));
      body = formData;
      headers = buildHeaders({ isMultipart: true });
    } else {
      body = JSON.stringify({
        test_id: currentTest.test_id,
        answers,
      });
      headers = buildHeaders();
    }

    const res = await fetch("/api/tests/grade", {
      method: "POST",
      headers,
      body,
    });
    if (!res.ok) {
      const msg = await extractErrorMessage(res, "Napaka pri ocenjevanju.");
      setStatus(msg, "error");
      return;
    }
    updateModelIndicatorFromResponse(res);
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
    updateModelIndicatorFromResponse(res);
    currentTest = await res.json();
    renderTest(currentTest);
    setStatus("Nov test je pripravljen.", "success");
  });
});

function renderTest(test) {
  clearAllSelectedImages();
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
      <div class="image-tools">
        <label class="mini">Dodaj sliko odgovora (telefon/kamera):</label>
        <input id="image-camera-${q.id}" class="hidden-file" type="file" accept="image/*" capture="environment" />
        <input id="image-gallery-${q.id}" class="hidden-file" type="file" accept="image/*" />
        <div class="upload-actions">
          <button type="button" class="secondary" id="camera-btn-${q.id}">Odpri kamero</button>
          <button type="button" class="secondary" id="gallery-btn-${q.id}">Izberi iz galerije</button>
          <button type="button" class="ghost hidden" id="clear-image-${q.id}">Odstrani sliko</button>
        </div>
        <p id="image-meta-${q.id}" class="mini hidden"></p>
        <img id="image-preview-${q.id}" class="image-preview hidden" alt="Predogled slike odgovora" />
      </div>
    `;

    wrap.innerHTML = `
      <span class="pill">${typeText}</span>
      <div><strong>${idx + 1}. ${q.question}</strong></div>
      ${optionsBlock}
      ${answerInput}
      ${imageInput}
    `;
    answersForm.appendChild(wrap);
    bindImageControls(String(q.id));
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
  clearAllSelectedImages();
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

function updateModelIndicatorFromResponse(response) {
  if (!modelIndicator || !response || !response.headers) return;
  const used = response.headers.get("X-AI-Model-Used");
  const configured = response.headers.get("X-AI-Model-Configured");
  if (!used && !configured) return;

  if (used === "mock") {
    modelIndicator.textContent = "AI model: mock (OPENAI_API_KEY ni nastavljen).";
    return;
  }

  if (used && configured && used !== configured) {
    modelIndicator.textContent = `AI model: ${used} (fallback iz ${configured}).`;
    return;
  }

  modelIndicator.textContent = `AI model: ${used || configured}.`;
}

function bindImageControls(questionId) {
  const cameraInput = document.getElementById(`image-camera-${questionId}`);
  const galleryInput = document.getElementById(`image-gallery-${questionId}`);
  const cameraBtn = document.getElementById(`camera-btn-${questionId}`);
  const galleryBtn = document.getElementById(`gallery-btn-${questionId}`);
  const clearBtn = document.getElementById(`clear-image-${questionId}`);

  if (cameraBtn && cameraInput) {
    cameraBtn.addEventListener("click", () => cameraInput.click());
  }
  if (galleryBtn && galleryInput) {
    galleryBtn.addEventListener("click", () => galleryInput.click());
  }
  if (clearBtn) {
    clearBtn.addEventListener("click", () => clearSelectedImage(questionId));
  }
  if (cameraInput) {
    cameraInput.addEventListener("change", () => onImageSelected(questionId, cameraInput.files?.[0] || null));
  }
  if (galleryInput) {
    galleryInput.addEventListener("change", () => onImageSelected(questionId, galleryInput.files?.[0] || null));
  }
}

function onImageSelected(questionId, file) {
  if (!file) return;
  if (!String(file.type || "").startsWith("image/")) {
    setStatus("Datoteka mora biti slika.", "error");
    return;
  }

  setSelectedImage(questionId, file);
  setStatus("Slika odgovora je dodana.", "success");
}

function setSelectedImage(questionId, file) {
  clearSelectedImage(questionId, { silent: true });
  selectedImages.set(questionId, file);

  const imageMeta = document.getElementById(`image-meta-${questionId}`);
  const imagePreview = document.getElementById(`image-preview-${questionId}`);
  const clearBtn = document.getElementById(`clear-image-${questionId}`);
  const cameraInput = document.getElementById(`image-camera-${questionId}`);
  const galleryInput = document.getElementById(`image-gallery-${questionId}`);

  const objectUrl = URL.createObjectURL(file);
  previewUrls.set(questionId, objectUrl);

  if (imageMeta) {
    const sizeKB = Math.max(1, Math.round(file.size / 1024));
    imageMeta.textContent = `${file.name} (${sizeKB} KB)`;
    imageMeta.classList.remove("hidden");
  }
  if (imagePreview) {
    imagePreview.src = objectUrl;
    imagePreview.classList.remove("hidden");
  }
  if (clearBtn) {
    clearBtn.classList.remove("hidden");
  }
  if (cameraInput) cameraInput.value = "";
  if (galleryInput) galleryInput.value = "";
}

function clearSelectedImage(questionId, options = {}) {
  selectedImages.delete(questionId);

  const oldUrl = previewUrls.get(questionId);
  if (oldUrl) {
    URL.revokeObjectURL(oldUrl);
    previewUrls.delete(questionId);
  }

  const imageMeta = document.getElementById(`image-meta-${questionId}`);
  const imagePreview = document.getElementById(`image-preview-${questionId}`);
  const clearBtn = document.getElementById(`clear-image-${questionId}`);
  const cameraInput = document.getElementById(`image-camera-${questionId}`);
  const galleryInput = document.getElementById(`image-gallery-${questionId}`);

  if (imageMeta) {
    imageMeta.textContent = "";
    imageMeta.classList.add("hidden");
  }
  if (imagePreview) {
    imagePreview.removeAttribute("src");
    imagePreview.classList.add("hidden");
  }
  if (clearBtn) {
    clearBtn.classList.add("hidden");
  }
  if (cameraInput) cameraInput.value = "";
  if (galleryInput) galleryInput.value = "";

  if (!options.silent) {
    setStatus("Slika odgovora je odstranjena.", "info");
  }
}

function clearAllSelectedImages() {
  const keys = Array.from(previewUrls.keys());
  keys.forEach((questionId) => {
    const oldUrl = previewUrls.get(questionId);
    if (oldUrl) URL.revokeObjectURL(oldUrl);
  });
  selectedImages.clear();
  previewUrls.clear();
}
