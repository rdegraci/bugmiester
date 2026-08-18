(() => {
  "use strict";

  const els = {
    status: document.getElementById("ops-status"),
    btnAnalyze: document.getElementById("btn-analyze"),
    kpiReports: document.getElementById("kpi-reports"),
    kpiDegraded: document.getElementById("kpi-degraded"),
    kpiGenerate: document.getElementById("kpi-generate"),
    kpiJudge: document.getElementById("kpi-judge"),
    reasonsBody: document.getElementById("reasons-body"),
    alertsList: document.getElementById("alerts-list"),
    reportsBody: document.getElementById("reports-body"),
    reportDetail: document.getElementById("report-detail"),
    filterReason: document.getElementById("filter-reason"),
  };

  const state = {
    busy: false,
    selectedId: null,
  };

  function setStatus(message) {
    els.status.textContent = message || "";
  }

  function clearChildren(el) {
    while (el.firstChild) {
      el.removeChild(el.firstChild);
    }
  }

  function pct(value) {
    const n = Number(value) || 0;
    return `${Math.round(n * 1000) / 10}%`;
  }

  function ms(value) {
    const n = Number(value) || 0;
    if (n >= 1000) {
      return `${(n / 1000).toFixed(1)}s`;
    }
    return `${Math.round(n)}ms`;
  }

  async function api(path, options) {
    const response = await fetch(path, {
      headers: { Accept: "application/json", "Content-Type": "application/json" },
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
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function renderSummary(summary) {
    const metrics = (summary && summary.metrics) || {};
    els.kpiReports.textContent = String(
      summary && summary.report_count != null ? summary.report_count : 0
    );
    els.kpiDegraded.textContent = pct(metrics.degraded_rate);
    els.kpiGenerate.textContent = ms(metrics.avg_generate_ms);
    els.kpiJudge.textContent = pct(metrics.judge_call_rate);

    clearChildren(els.reasonsBody);
    const reasons = (summary && summary.reasons) || {};
    const reasonEntries = Object.keys(reasons).sort();
    if (!reasonEntries.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 2;
      cell.className = "text-secondary";
      cell.textContent = "No data yet.";
      row.appendChild(cell);
      els.reasonsBody.appendChild(row);
    } else {
      reasonEntries.forEach((reason) => {
        const row = document.createElement("tr");
        const name = document.createElement("td");
        name.textContent = reason;
        const count = document.createElement("td");
        count.className = "text-end";
        count.textContent = String(reasons[reason] || 0);
        row.appendChild(name);
        row.appendChild(count);
        els.reasonsBody.appendChild(row);
      });
    }

    clearChildren(els.alertsList);
    const alerts = (summary && summary.alerts) || [];
    if (!alerts.length) {
      const item = document.createElement("li");
      item.className = "text-secondary";
      item.textContent = "No alerts.";
      els.alertsList.appendChild(item);
    } else {
      alerts.forEach((text) => {
        const item = document.createElement("li");
        item.className = "ops-alert";
        item.textContent = text;
        els.alertsList.appendChild(item);
      });
    }

    if (summary && summary.generated_at) {
      setStatus(
        `Updated ${summary.generated_at} · ${summary.round_log_count || 0} round logs`
      );
    }
  }

  function renderReports(reports) {
    clearChildren(els.reportsBody);
    if (!reports || !reports.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 3;
      cell.className = "text-secondary";
      cell.textContent = "No reports yet.";
      row.appendChild(cell);
      els.reportsBody.appendChild(row);
      return;
    }

    reports.forEach((report) => {
      const row = document.createElement("tr");
      row.className = "ops-report-row";
      if (report.report_id === state.selectedId) {
        row.classList.add("ops-report-selected");
      }
      row.tabIndex = 0;
      row.dataset.reportId = report.report_id || "";

      const when = document.createElement("td");
      when.textContent = report.created_at || "—";
      const reason = document.createElement("td");
      reason.textContent = report.reason || "—";
      const category = document.createElement("td");
      category.textContent = report.bug_category || "—";

      row.appendChild(when);
      row.appendChild(reason);
      row.appendChild(category);

      row.addEventListener("click", () => {
        if (report.report_id) {
          loadReportDetail(report.report_id);
        }
      });
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          if (report.report_id) {
            loadReportDetail(report.report_id);
          }
        }
      });

      els.reportsBody.appendChild(row);
    });
  }

  function renderDetail(report) {
    clearChildren(els.reportDetail);
    if (!report) {
      const empty = document.createElement("p");
      empty.className = "text-secondary mb-0";
      empty.textContent = "Select a report.";
      els.reportDetail.appendChild(empty);
      return;
    }

    function addField(label, value) {
      const wrap = document.createElement("div");
      wrap.className = "mb-2";
      const title = document.createElement("div");
      title.className = "ops-detail-label";
      title.textContent = label;
      const body = document.createElement("div");
      body.className = "ops-detail-value";
      body.textContent = value == null || value === "" ? "—" : String(value);
      wrap.appendChild(title);
      wrap.appendChild(body);
      els.reportDetail.appendChild(wrap);
    }

    addField("Reason", report.reason);
    addField("Category", report.bug_category);
    addField("Seed", report.seed_id);
    addField("Player answer", report.player_answer);
    addField("Expected", report.bug_summary);
    addField(
      "Score",
      report.points_awarded != null
        ? `${report.points_awarded} / ${report.points_possible ?? "?"}`
        : ""
    );
    addField("Note", report.note);

    const codeLabel = document.createElement("div");
    codeLabel.className = "ops-detail-label";
    codeLabel.textContent = "Code";
    els.reportDetail.appendChild(codeLabel);
    const pre = document.createElement("pre");
    pre.className = "code-well mb-0";
    const code = document.createElement("code");
    code.textContent = report.code || "";
    pre.appendChild(code);
    els.reportDetail.appendChild(pre);
  }

  async function loadReportDetail(reportId) {
    state.selectedId = reportId;
    try {
      const report = await api(`/api/ops/reports/${encodeURIComponent(reportId)}`);
      renderDetail(report);
      // Refresh selection highlight without refetching list data shape.
      Array.from(els.reportsBody.querySelectorAll("tr[data-report-id]")).forEach(
        (row) => {
          row.classList.toggle(
            "ops-report-selected",
            row.dataset.reportId === reportId
          );
        }
      );
    } catch (err) {
      setStatus(err.message || "Failed to load report");
      renderDetail(null);
    }
  }

  async function loadReports() {
    const reason = (els.filterReason && els.filterReason.value) || "";
    const query = reason
      ? `?limit=50&reason=${encodeURIComponent(reason)}`
      : "?limit=50";
    const reports = await api(`/api/ops/reports${query}`);
    renderReports(reports);
  }

  async function loadSummary() {
    const summary = await api("/api/ops/summary");
    renderSummary(summary);
  }

  async function refreshAll() {
    if (state.busy) return;
    state.busy = true;
    els.btnAnalyze.disabled = true;
    setStatus("Loading…");
    try {
      await loadSummary();
      await loadReports();
    } catch (err) {
      setStatus(err.message || "Failed to load ops data");
    } finally {
      state.busy = false;
      els.btnAnalyze.disabled = false;
    }
  }

  async function onAnalyze() {
    if (state.busy) return;
    state.busy = true;
    els.btnAnalyze.disabled = true;
    setStatus("Running analyze…");
    try {
      const summary = await api("/api/ops/analyze", { method: "POST" });
      renderSummary(summary);
      await loadReports();
      setStatus(
        `Analyze complete · ${summary.report_count || 0} reports · ${
          summary.round_log_count || 0
        } round logs`
      );
    } catch (err) {
      setStatus(err.message || "Analyze failed");
    } finally {
      state.busy = false;
      els.btnAnalyze.disabled = false;
    }
  }

  els.btnAnalyze.addEventListener("click", onAnalyze);
  els.filterReason.addEventListener("change", () => {
    loadReports().catch((err) => {
      setStatus(err.message || "Failed to filter reports");
    });
  });

  renderDetail(null);
  refreshAll();
})();
