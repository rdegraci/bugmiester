(() => {
  "use strict";

  const placeholder = document.getElementById("ops-summary-placeholder");
  const body = document.getElementById("ops-summary-body");
  const btnAnalyze = document.getElementById("btn-analyze");

  function showPlaceholder(text) {
    placeholder.textContent = text;
    placeholder.classList.remove("d-none");
    placeholder.hidden = false;
    body.classList.add("d-none");
    body.hidden = true;
    body.textContent = "";
  }

  function showSummary(text) {
    placeholder.classList.add("d-none");
    placeholder.hidden = true;
    body.classList.remove("d-none");
    body.hidden = false;
    body.textContent = text;
  }

  async function runAnalyze() {
    btnAnalyze.disabled = true;
    showPlaceholder("Analyze (not connected yet).");
    try {
      const response = await fetch("/api/ops/analyze", { method: "POST" });
      if (!response.ok) {
        showPlaceholder("Summary will load here.");
        return;
      }
      const data = await response.json();
      showSummary(JSON.stringify(data, null, 2));
    } catch (_err) {
      // File:// or no server — keep the Slice 03 placeholder.
      showPlaceholder("Summary will load here.");
    } finally {
      btnAnalyze.disabled = false;
    }
  }

  btnAnalyze.addEventListener("click", runAnalyze);
  showPlaceholder("Summary will load here.");
})();
