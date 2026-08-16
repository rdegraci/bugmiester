(() => {
  "use strict";

  const els = {
    setupBanner: document.getElementById("setup-banner"),
    setupBannerMessage: document.getElementById("setup-banner-message"),
    bugIndex: document.getElementById("bug-index"),
    bugsPerRound: document.getElementById("bugs-per-round"),
    roundScore: document.getElementById("round-score"),
    roundPossible: document.getElementById("round-possible"),
    progressStatus: document.getElementById("progress-status"),
    degradedIndicator: document.getElementById("degraded-indicator"),
    codeContent: document.getElementById("code-content"),
    answerForm: document.getElementById("answer-form"),
    answerInput: document.getElementById("answer-input"),
    btnStart: document.getElementById("btn-start"),
    btnSubmit: document.getElementById("btn-submit"),
    btnNext: document.getElementById("btn-next"),
    btnReport: document.getElementById("btn-report"),
    feedbackPanel: document.getElementById("feedback-panel"),
    feedbackText: document.getElementById("feedback-text"),
    expectedSummary: document.getElementById("expected-summary"),
    btnPlayAgain: document.getElementById("btn-play-again"),
    modalScore: document.getElementById("modal-score"),
    modalPossible: document.getElementById("modal-possible"),
  };

  const state = {
    busy: false,
    hasFeedback: false,
  };

  function setHidden(el, hidden) {
    if (!el) return;
    el.hidden = hidden;
    el.classList.toggle("d-none", hidden);
  }

  function setCode(text) {
    // Always textContent — never innerHTML for snippet text.
    els.codeContent.textContent = text;
  }

  function setProgress(message) {
    els.progressStatus.textContent = message || "";
  }

  function setBusy(busy) {
    state.busy = busy;
    els.btnStart.disabled = busy;
    els.btnSubmit.disabled = busy || !els.answerInput.value.trim();
    els.btnNext.disabled = busy || !state.hasFeedback;
    els.btnReport.disabled = busy || !state.hasFeedback;
    els.answerInput.disabled = busy;
  }

  function showSetupBanner(message) {
    els.setupBannerMessage.textContent =
      message || "Configure your API key to play.";
    setHidden(els.setupBanner, false);
  }

  function hideSetupBanner() {
    setHidden(els.setupBanner, true);
  }

  function showFeedback(message, expected) {
    els.feedbackText.textContent = message;
    els.expectedSummary.textContent = expected
      ? `Expected: ${expected}`
      : "";
    els.feedbackPanel.classList.remove("alert-success", "alert-danger", "alert-warning");
    els.feedbackPanel.classList.add("alert-secondary");
    setHidden(els.feedbackPanel, false);
    state.hasFeedback = true;
    setHidden(els.btnReport, false);
    els.btnReport.disabled = false;
    els.btnNext.disabled = false;
  }

  function clearFeedback() {
    setHidden(els.feedbackPanel, true);
    els.feedbackText.textContent = "";
    els.expectedSummary.textContent = "";
    state.hasFeedback = false;
    setHidden(els.btnReport, true);
    els.btnReport.disabled = true;
    els.btnNext.disabled = true;
  }

  function setDegraded(visible) {
    setHidden(els.degradedIndicator, !visible);
  }

  // Placeholder handlers — real API wiring comes in later slices.
  function onStart() {
    if (state.busy) return;
    setBusy(true);
    setProgress("Start round (not connected yet).");
    clearFeedback();
    setDegraded(false);
    setCode("// Slice 03 shell — connect APIs in Slice 05+.");
    els.answerInput.value = "";
    els.answerInput.disabled = false;
    els.btnSubmit.disabled = true;
    setBusy(false);
    setProgress("");
  }

  function onSubmit(event) {
    event.preventDefault();
    if (state.busy) return;
    const answer = els.answerInput.value.trim();
    if (!answer) return;
    setBusy(true);
    setProgress("Submit (not connected yet).");
    showFeedback(
      "Placeholder feedback — scoring API not wired yet.",
      "Expected summary will appear here."
    );
    setBusy(false);
    setProgress("");
  }

  function onNext() {
    if (state.busy || !state.hasFeedback) return;
    setBusy(true);
    setProgress("Next bug (not connected yet).");
    clearFeedback();
    setCode("// Next snippet will load here.");
    els.answerInput.value = "";
    setBusy(false);
    setProgress("");
  }

  function onReport() {
    if (state.busy || !state.hasFeedback) return;
    setProgress("Report snippet (not connected yet).");
  }

  function onPlayAgain() {
    onStart();
  }

  function onAnswerInput() {
    els.btnSubmit.disabled = state.busy || !els.answerInput.value.trim();
  }

  els.btnStart.addEventListener("click", onStart);
  els.answerForm.addEventListener("submit", onSubmit);
  els.btnNext.addEventListener("click", onNext);
  els.btnReport.addEventListener("click", onReport);
  els.btnPlayAgain.addEventListener("click", onPlayAgain);
  els.answerInput.addEventListener("input", onAnswerInput);

  // Safe no-op health probe for later slices; ignore failures offline.
  async function probeHealth() {
    try {
      const response = await fetch("/api/health");
      if (!response.ok) return;
      const data = await response.json();
      if (data && data.config_ready === false) {
        showSetupBanner(data.message || "Configure your API key to play.");
      } else {
        hideSetupBanner();
      }
    } catch (_err) {
      // File:// or no server — stay quiet in Slice 03.
      hideSetupBanner();
    }
  }

  setCode("Start a round to load a Swift snippet.");
  clearFeedback();
  setDegraded(false);
  setBusy(false);
  els.answerInput.disabled = true;
  probeHealth();
})();
