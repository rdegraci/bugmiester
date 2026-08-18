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
    reportControls: document.getElementById("report-controls"),
    reportReason: document.getElementById("report-reason"),
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
    nextBugNumber: 1,
    roundComplete: false,
    configReady: false,
    reportedCurrent: false,
    prefetchEnabled: true,
    prefetch: {
      token: 0,
      roundId: null,
      promise: null,
      bug: null,
      error: null,
      inFlight: false,
    },
  };

  function setHidden(el, hidden) {
    if (!el) return;
    el.hidden = hidden;
    el.classList.toggle("d-none", hidden);
  }

  function setCode(text) {
    // Model / API code must never use innerHTML.
    els.codeContent.textContent = text;
  }

  function setProgress(message) {
    els.progressStatus.textContent = message || "";
  }

  function bugsPerRound() {
    return Number(els.bugsPerRound.textContent) || 10;
  }

  function formatApiError(err) {
    const msg = (err && err.message) || "Request failed";
    const status = err && err.status;
    if (status === 503) {
      return msg.indexOf("503") >= 0 ? msg : `${msg} (503)`;
    }
    if (status === 502) {
      return msg.indexOf("502") >= 0
        ? msg
        : `${msg} (502 — LLM request failed)`;
    }
    return msg;
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
    if (typeof data.index === "number") {
      const display =
        state.snippetId != null
          ? data.index + 1
          : Math.min(data.index, bugsPerRound());
      els.bugIndex.textContent = String(display);
    }
  }

  function setBusy(busy) {
    state.busy = busy;
    const answering =
      Boolean(state.snippetId) && !state.hasFeedback && !state.roundComplete;
    // Prefetch runs in the background — do not lock Report / reading feedback.
    els.btnStart.disabled = busy;
    els.btnSubmit.disabled =
      busy || !answering || !els.answerInput.value.trim();
    els.btnNext.disabled =
      busy || !state.hasFeedback || state.roundComplete || !state.roundId;
    els.btnReport.disabled =
      busy || !state.hasFeedback || state.reportedCurrent || !state.snippetId;
    if (els.reportReason) {
      els.reportReason.disabled =
        busy || !state.hasFeedback || state.reportedCurrent;
    }
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
    state.reportedCurrent = false;
    setHidden(els.reportControls, false);
  }

  function clearFeedback() {
    setHidden(els.feedbackPanel, true);
    els.feedbackText.textContent = "";
    els.expectedSummary.textContent = "";
    state.hasFeedback = false;
    state.reportedCurrent = false;
    setHidden(els.reportControls, true);
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

  function invalidatePrefetch() {
    state.prefetch.token += 1;
    state.prefetch.promise = null;
    state.prefetch.bug = null;
    state.prefetch.error = null;
    state.prefetch.inFlight = false;
    state.prefetch.roundId = null;
  }

  function clearPrefetchResult() {
    state.prefetch.bug = null;
    state.prefetch.error = null;
    state.prefetch.promise = null;
    state.prefetch.inFlight = false;
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
      const err = new Error(
        typeof detail === "string" ? detail : JSON.stringify(detail)
      );
      err.status = response.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function applyBug(bug) {
    const n = state.nextBugNumber;
    state.snippetId = bug.snippet_id;
    state.hasFeedback = false;
    state.reportedCurrent = false;
    state.roundComplete = false;
    state.nextBugNumber =
      (typeof bug.index === "number" ? bug.index : n - 1) + 2;
    updateRoundChrome(bug);
    setCode(bug.code || "");
    setDegraded(Boolean(bug.degraded));
    els.answerInput.value = "";
    clearFeedback();
    setProgress("");
    setBusy(false);
  }

  async function requestNextBug(showProgress) {
    const n = state.nextBugNumber;
    if (showProgress) {
      setProgress(`Generating bug ${n}/${bugsPerRound()}…`);
    }
    return api("/api/round/next-bug", {
      method: "POST",
      body: JSON.stringify({ round_id: state.roundId }),
    });
  }

  function startPrefetch() {
    if (
      !state.prefetchEnabled ||
      state.roundComplete ||
      !state.roundId ||
      state.prefetch.inFlight
    ) {
      return;
    }
    const token = state.prefetch.token + 1;
    state.prefetch.token = token;
    const roundId = state.roundId;
    const n = state.nextBugNumber;
    state.prefetch.roundId = roundId;
    state.prefetch.bug = null;
    state.prefetch.error = null;
    state.prefetch.inFlight = true;
    setProgress(`Preparing bug ${n}/${bugsPerRound()}…`);

    const promise = requestNextBug(false)
      .then((bug) => {
        if (
          token !== state.prefetch.token ||
          roundId !== state.roundId ||
          state.roundComplete
        ) {
          // Stale: a newer round started or round ended — ignore.
          return null;
        }
        state.prefetch.bug = bug;
        state.prefetch.inFlight = false;
        if (state.hasFeedback && !state.busy) {
          setProgress(`Bug ${n}/${bugsPerRound()} ready`);
        }
        return bug;
      })
      .catch((err) => {
        if (token !== state.prefetch.token || roundId !== state.roundId) {
          return null;
        }
        state.prefetch.error = err;
        state.prefetch.inFlight = false;
        if (state.hasFeedback && !state.busy) {
          setProgress("");
        }
        return null;
      });

    state.prefetch.promise = promise;
  }

  async function fetchNextBug() {
    const bug = await requestNextBug(true);
    applyBug(bug);
  }

  async function takePrefetchedOrFetch() {
    // Prefer a completed prefetch for this round (avoids double next-bug).
    if (
      state.prefetch.bug &&
      state.prefetch.roundId === state.roundId &&
      !state.roundComplete
    ) {
      const bug = state.prefetch.bug;
      clearPrefetchResult();
      applyBug(bug);
      return;
    }

    // Await in-flight prefetch for this round instead of issuing a second call.
    if (
      state.prefetch.promise &&
      state.prefetch.roundId === state.roundId &&
      !state.roundComplete
    ) {
      setProgress(
        `Generating bug ${state.nextBugNumber}/${bugsPerRound()}…`
      );
      await state.prefetch.promise;
      if (
        state.prefetch.bug &&
        state.prefetch.roundId === state.roundId &&
        !state.roundComplete
      ) {
        const bug = state.prefetch.bug;
        clearPrefetchResult();
        applyBug(bug);
        return;
      }
      // Prefetch failed or was cancelled — fall through to a fresh request.
      clearPrefetchResult();
    }

    await fetchNextBug();
  }

  async function onStart() {
    if (state.busy) return;
    setBusy(true);
    invalidatePrefetch();
    clearFeedback();
    setDegraded(false);
    state.snippetId = null;
    state.roundComplete = false;
    state.nextBugNumber = 1;
    try {
      setProgress("Starting round…");
      const started = await api("/api/round/start", {
        method: "POST",
        body: "{}",
      });
      state.roundId = started.round_id;
      updateRoundChrome(started);
      els.bugIndex.textContent = "0";
      await fetchNextBug();
    } catch (err) {
      setProgress("");
      setCode(formatApiError(err) || "Could not start round.");
      showSetupBanner(formatApiError(err) || "Failed to start round");
      setBusy(false);
    }
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (state.busy || !state.roundId || !state.snippetId || state.hasFeedback) {
      return;
    }
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
        invalidatePrefetch();
        showRoundCompleteModal(result);
        els.btnNext.disabled = true;
      } else if (state.prefetchEnabled) {
        startPrefetch();
      }
    } catch (err) {
      setProgress("");
      showFeedback({
        correct: false,
        partial: false,
        feedback: formatApiError(err) || "Submit failed",
        expected_summary: "",
      });
      setBusy(false);
    }
  }

  async function onNext() {
    if (
      state.busy ||
      !state.hasFeedback ||
      state.roundComplete ||
      !state.roundId
    ) {
      return;
    }
    setBusy(true);
    try {
      await takePrefetchedOrFetch();
    } catch (err) {
      clearPrefetchResult();
      setProgress("");
      setCode(formatApiError(err) || "Could not load next bug.");
      setBusy(false);
    }
  }

  async function onReport() {
    if (
      state.busy ||
      !state.hasFeedback ||
      !state.roundId ||
      !state.snippetId ||
      state.reportedCurrent
    ) {
      return;
    }
    const reason = (els.reportReason && els.reportReason.value) || "other";
    // Keep current snippet_id for report even if prefetch already advanced server pending.
    const snippetId = state.snippetId;
    setBusy(true);
    setProgress("Sending report…");
    try {
      await api("/api/round/report-snippet", {
        method: "POST",
        body: JSON.stringify({
          round_id: state.roundId,
          snippet_id: snippetId,
          reason,
          note: "",
        }),
      });
      state.reportedCurrent = true;
      setProgress("Report saved.");
      setBusy(false);
      // Restore soft prefetch status if a next bug is already ready.
      if (state.prefetch.bug && !state.roundComplete) {
        setProgress(
          `Bug ${state.nextBugNumber}/${bugsPerRound()} ready`
        );
      } else if (state.prefetch.inFlight && !state.roundComplete) {
        setProgress(
          `Preparing bug ${state.nextBugNumber}/${bugsPerRound()}…`
        );
      }
    } catch (err) {
      setProgress(formatApiError(err) || "Report failed");
      setBusy(false);
    }
  }

  function onPlayAgain() {
    onStart();
  }

  function onAnswerInput() {
    const answering =
      Boolean(state.snippetId) && !state.hasFeedback && !state.roundComplete;
    els.btnSubmit.disabled =
      state.busy || !answering || !els.answerInput.value.trim();
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
      if (typeof data.prefetch_next_bug === "boolean") {
        state.prefetchEnabled = data.prefetch_next_bug;
      }
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
