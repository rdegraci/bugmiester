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
    roundCompleteModal: document.getElementById("round-complete-modal"),
  };

  const state = {
    busy: false,
    hasFeedback: false,
    roundId: null,
    snippetId: null,
    roundComplete: false,
    configReady: false,
  };

  function setHidden(el, hidden) {
    if (!el) return;
    el.hidden = hidden;
    el.classList.toggle("d-none", hidden);
  }

  function setCode(text) {
    els.codeContent.textContent = text;
  }

  function setProgress(message) {
    els.progressStatus.textContent = message || "";
  }

  function updateRoundChrome(data) {
    if (typeof data.bugs_per_round === "number") {
      els.bugsPerRound.textContent = String(data.bugs_per_round);
    }
    if (typeof data.round_score === "number") {
      els.roundScore.textContent = String(data.round_score);
    }
    if (typeof data.round_possible === "number") {
      els.roundPossible.textContent = String(data.round_possible);
    }
    if (typeof data.index === "number" && typeof data.bugs_per_round === "number") {
      // Display 1-based while a bug is active; 0 before first next-bug.
      const display =
        state.snippetId != null ? data.index + 1 : Math.min(data.index, data.bugs_per_round);
      els.bugIndex.textContent = String(display);
    }
  }

  function setBusy(busy) {
    state.busy = busy;
    const answering = Boolean(state.snippetId) && !state.hasFeedback && !state.roundComplete;
    els.btnStart.disabled = busy;
    els.btnSubmit.disabled = busy || !answering || !els.answerInput.value.trim();
    els.btnNext.disabled =
      busy || !state.hasFeedback || state.roundComplete || !state.roundId;
    els.btnReport.disabled = busy || !state.hasFeedback;
    els.answerInput.disabled = busy || !answering;
  }

  function showSetupBanner(message) {
    els.setupBannerMessage.textContent =
      message || "Configure your API key to play.";
    setHidden(els.setupBanner, false);
  }

  function showSetupFromHealth(data) {
    const missing = data.missing_key || "API key";
    const envPath = data.env_path || "";
    const parts = [
      data.message || `Set ${missing} in ${envPath}`,
      envPath ? `env_path: ${envPath}` : "",
      data.missing_key ? `missing_key: ${data.missing_key}` : "",
      data.config_path ? `config_path: ${data.config_path}` : "",
      "For Slice 05, set llm.provider: mock in config.yaml",
    ].filter(Boolean);
    showSetupBanner(parts.join(" · "));
  }

  function hideSetupBanner() {
    setHidden(els.setupBanner, true);
  }

  function showFeedback(result) {
    els.feedbackText.textContent = result.feedback || "";
    els.expectedSummary.textContent = result.expected_summary
      ? `Expected: ${result.expected_summary}`
      : "";
    els.feedbackPanel.classList.remove(
      "alert-success",
      "alert-danger",
      "alert-warning",
      "alert-secondary"
    );
    if (result.correct) {
      els.feedbackPanel.classList.add("alert-success");
    } else if (result.partial) {
      els.feedbackPanel.classList.add("alert-warning");
    } else {
      els.feedbackPanel.classList.add("alert-danger");
    }
    setHidden(els.feedbackPanel, false);
    state.hasFeedback = true;
    setHidden(els.btnReport, false);
  }

  function clearFeedback() {
    setHidden(els.feedbackPanel, true);
    els.feedbackText.textContent = "";
    els.expectedSummary.textContent = "";
    state.hasFeedback = false;
    setHidden(els.btnReport, true);
  }

  function setDegraded(visible) {
    setHidden(els.degradedIndicator, !visible);
  }

  function showRoundCompleteModal(result) {
    const score =
      (result.summary && result.summary.round_score) || result.round_score || 0;
    const possible =
      (result.summary && result.summary.round_possible) ||
      result.round_possible ||
      100;
    els.modalScore.textContent = String(score);
    els.modalPossible.textContent = String(possible);
    if (window.bootstrap && els.roundCompleteModal) {
      const modal = window.bootstrap.Modal.getOrCreateInstance(
        els.roundCompleteModal
      );
      modal.show();
    }
  }

  async function api(path, options) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...options,
    });
    let data = null;
    try {
      data = await response.json();
    } catch (_err) {
      data = null;
    }
    if (!response.ok) {
      const detail =
        (data && data.detail && data.detail.message) ||
        (data && data.detail) ||
        response.statusText;
      const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      err.status = response.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  async function fetchNextBug() {
    setProgress(
      `Generating bug ${(Number(els.bugIndex.textContent) || 0) + 1}/${els.bugsPerRound.textContent}…`
    );
    const bug = await api("/api/round/next-bug", {
      method: "POST",
      body: JSON.stringify({ round_id: state.roundId }),
    });
    state.snippetId = bug.snippet_id;
    state.hasFeedback = false;
    state.roundComplete = false;
    updateRoundChrome(bug);
    setCode(bug.code || "");
    setDegraded(Boolean(bug.degraded));
    els.answerInput.value = "";
    clearFeedback();
    setProgress("");
    setBusy(false);
  }

  async function onStart() {
    if (state.busy) return;
    setBusy(true);
    clearFeedback();
    setDegraded(false);
    state.snippetId = null;
    state.roundComplete = false;
    try {
      setProgress("Starting round…");
      const started = await api("/api/round/start", { method: "POST", body: "{}" });
      state.roundId = started.round_id;
      updateRoundChrome(started);
      els.bugIndex.textContent = "0";
      await fetchNextBug();
    } catch (err) {
      setProgress("");
      setCode("Could not start round.");
      showSetupBanner(err.message || "Failed to start round");
      setBusy(false);
    }
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (state.busy || !state.roundId || !state.snippetId || state.hasFeedback) return;
    const answer = els.answerInput.value.trim();
    if (!answer) return;
    setBusy(true);
    setProgress("Scoring…");
    try {
      const result = await api("/api/round/submit", {
        method: "POST",
        body: JSON.stringify({
          round_id: state.roundId,
          snippet_id: state.snippetId,
          answer,
        }),
      });
      updateRoundChrome(result);
      showFeedback(result);
      state.roundComplete = Boolean(result.round_complete);
      setProgress("");
      setBusy(false);
      if (result.round_complete) {
        showRoundCompleteModal(result);
        els.btnNext.disabled = true;
      }
    } catch (err) {
      setProgress("");
      showFeedback({
        correct: false,
        partial: false,
        feedback: err.message || "Submit failed",
        expected_summary: "",
      });
      setBusy(false);
    }
  }

  async function onNext() {
    if (state.busy || !state.hasFeedback || state.roundComplete || !state.roundId) {
      return;
    }
    setBusy(true);
    try {
      await fetchNextBug();
    } catch (err) {
      setProgress("");
      setCode(err.message || "Could not load next bug.");
      setBusy(false);
    }
  }

  function onReport() {
    if (state.busy || !state.hasFeedback) return;
    setProgress("Report snippet (Slice 08).");
  }

  function onPlayAgain() {
    onStart();
  }

  function onAnswerInput() {
    const answering = Boolean(state.snippetId) && !state.hasFeedback && !state.roundComplete;
    els.btnSubmit.disabled = state.busy || !answering || !els.answerInput.value.trim();
  }

  els.btnStart.addEventListener("click", onStart);
  els.answerForm.addEventListener("submit", onSubmit);
  els.btnNext.addEventListener("click", onNext);
  els.btnReport.addEventListener("click", onReport);
  els.btnPlayAgain.addEventListener("click", onPlayAgain);
  els.answerInput.addEventListener("input", onAnswerInput);

  async function probeHealth() {
    try {
      const response = await fetch("/api/health");
      if (!response.ok) return;
      const data = await response.json();
      state.configReady = Boolean(data.config_ready);
      if (data && data.config_ready === false) {
        showSetupFromHealth(data);
      } else {
        hideSetupBanner();
      }
    } catch (_err) {
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
