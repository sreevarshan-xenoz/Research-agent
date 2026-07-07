/**
 * Unit tests for P26: Advanced AI Research Assistant
 * Tests renderHypotheses(), renderStrategy(), and renderGapExploration()
 *
 * Environment: jsdom via Vitest
 */

// ── Setup: DOM elements required by the functions ──────────────────────

function setupDOM() {
  document.body.innerHTML = `
    <div id="hypothesisPanel" class="p26-panel"></div>
    <span class="badge small" id="hypothesisBadge">0</span>
    <div id="strategyPanel" class="p26-panel"></div>
    <span class="badge small" id="strategyBadge">Ready</span>
  `;
}

// ── Implementation under test ──────────────────────────────────────────

function renderHypotheses(hypotheses) {
  const panel = document.getElementById("hypothesisPanel");
  const badge = document.getElementById("hypothesisBadge");
  if (!panel) return;
  if (!hypotheses || !Array.isArray(hypotheses) || hypotheses.length === 0) {
    panel.innerHTML =
      '<p class="small muted">No hypotheses generated yet.</p>';
    if (badge) badge.textContent = "0";
    return;
  }
  if (badge) badge.textContent = String(hypotheses.length);
  const gapColors = {
    methodology: "#8b5cf6",
    evaluation: "#06b6d4",
    coverage: "#f59e0b",
    general: "#71717a",
  };
  panel.innerHTML = hypotheses
    .map((h) => {
      const gap = (h.gap_addressed || "general").toLowerCase();
      const badgeColor = gapColors[gap] || gapColors.general;
      const novelty = Math.min(100, Math.max(0, Math.round((h.novelty || 0) * 100)));
      const feasibility = Math.min(100, Math.max(0, Math.round((h.feasibility || 0) * 100)));
      return `
        <div class="p26-card">
          <div class="p26-card-header">
            <span class="p26-card-title">${h.title || "Untitled Hypothesis"}</span>
            <span class="p26-badge" style="background: ${badgeColor}22; color: ${badgeColor}; border: 1px solid ${badgeColor}44;">
              ${gap}
            </span>
          </div>
          <div class="p26-card-body">
            <p class="p26-card-stmt">${h.statement || ""}</p>
            ${h.rationale ? `<p class="p26-card-rationale">${h.rationale}</p>` : ""}
          </div>
          <div class="p26-score-row">
            <div class="p26-score-item">
              <span class="p26-score-label">Novelty</span>
              <div class="p26-score-bar"><div class="p26-score-fill" style="width:${novelty}%"></div></div>
              <span class="p26-score-val">${novelty}%</span>
            </div>
            <div class="p26-score-item">
              <span class="p26-score-label">Feasibility</span>
              <div class="p26-score-bar"><div class="p26-score-fill" style="width:${feasibility}%"></div></div>
              <span class="p26-score-val">${feasibility}%</span>
            </div>
          </div>
          ${h.proposed_approach ? `<div class="p26-card-detail"><strong>Approach:</strong> ${h.proposed_approach}</div>` : ""}
          ${h.evaluation_approach ? `<div class="p26-card-detail"><strong>Evaluation:</strong> ${h.evaluation_approach}</div>` : ""}
          ${h.required_resources && h.required_resources.length > 0
            ? `<div class="p26-card-tags">${h.required_resources.map(r => `<span class="p26-tag">${r}</span>`).join("")}</div>`
            : ""}
        </div>
      `;
    })
    .join("");
}

function renderStrategy(strategy) {
  const panel = document.getElementById("strategyPanel");
  const badge = document.getElementById("strategyBadge");
  if (!panel) return;
  if (!strategy || !strategy.methodology) {
    panel.innerHTML =
      '<p class="small muted">No strategy recommendations yet.</p>';
    if (badge) badge.textContent = "Ready";
    return;
  }
  if (badge) badge.textContent = "Ready";
  let html = "";

  // Methodology
  if (strategy.methodology) {
    html += '<div class="p26-section-label">Methodology</div>';
    if (strategy.methodology.recommended_approaches) {
      strategy.methodology.recommended_approaches.forEach((a) => {
        html += `
          <div class="p26-card">
            <div class="p26-card-header">
              <span class="p26-card-title-small">${a.name || ""}</span>
            </div>
            <div class="p26-card-body">
              <p class="p26-card-desc">${a.description || ""}</p>
              ${a.rationale ? `<p class="p26-card-rationale">${a.rationale}</p>` : ""}
            </div>
          </div>
        `;
      });
    }
    if (strategy.methodology.avoid && strategy.methodology.avoid.length > 0) {
      html += '<div class="p26-card-avoid">';
      html += '<span class="p26-avoid-label">Avoid</span>';
      strategy.methodology.avoid.forEach((a) => {
        html += `<span class="p26-avoid-chip">${a}</span>`;
      });
      html += "</div>";
    }
  }

  // Datasets
  if (strategy.datasets && strategy.datasets.recommended) {
    html +=
      '<div class="p26-section-label" style="margin-top: 8px;">Datasets</div>';
    strategy.datasets.recommended.forEach((d) => {
      html += `
        <div class="p26-card p26-card-compact">
          <span class="p26-card-title-small">${d.name || ""}</span>
          <p class="p26-card-desc">${d.description || ""}</p>
        </div>
      `;
    });
  }

  // Baselines
  if (strategy.baselines && strategy.baselines.recommended) {
    html +=
      '<div class="p26-section-label" style="margin-top: 8px;">Baselines</div>';
    strategy.baselines.recommended.forEach((b) => {
      html += `
        <div class="p26-card p26-card-compact">
          <span class="p26-card-title-small">${b.name || ""}</span>
          <p class="p26-card-desc">${b.description || ""}</p>
        </div>
      `;
    });
  }

  // Evaluation
  if (strategy.evaluation) {
    html +=
      '<div class="p26-section-label" style="margin-top: 8px;">Evaluation</div>';
    if (strategy.evaluation.primary_metrics) {
      html +=
        '<div class="p26-card-tags">' +
        strategy.evaluation.primary_metrics
          .map((m) => `<span class="p26-tag">${m}</span>`)
          .join("") +
        "</div>";
    }
    if (strategy.evaluation.ablation) {
      html +=
        '<div class="p26-card-detail" style="margin-top: 4px;"><strong>Ablation:</strong> ' +
        (Array.isArray(strategy.evaluation.ablation)
          ? strategy.evaluation.ablation.join("; ")
          : strategy.evaluation.ablation) +
        "</div>";
    }
  }

  panel.innerHTML = html;
}

function renderGapExploration(gapExp) {
  if (!gapExp || !gapExp.is_thin) return;
  const panel = document.getElementById("hypothesisPanel");
  if (!panel) return;
  // Add gap exploration note at the top of the hypothesis panel
  const note = document.createElement("div");
  note.className = "p26-card p26-thin-note";
  note.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
      <span style="font-size: 1rem;">⚠️</span>
      <span style="font-weight: 600; font-size: 0.75rem; color: #f59e0b;">Thin Literature Detected</span>
    </div>
    <p style="font-size: 0.7rem; color: #a1a1aa; margin: 0; line-height: 1.4;">${gapExp.analysis || ""}</p>
    <div style="display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap;">
      ${(gapExp.alternative_queries || []).map((q) => `<span class="p26-tag p26-tag-alt">${q}</span>`).join("")}
    </div>
    <div style="margin-top: 6px; font-size: 0.65rem; color: #f59e0b; font-weight: 600; text-transform: uppercase;">
      Recommendation: ${(gapExp.recommendation || "").replace(/_/g, " ")}
    </div>
  `;
  panel.insertBefore(note, panel.firstChild);
}

// ── Tests ──────────────────────────────────────────────────────────────

describe("renderHypotheses", () => {
  beforeEach(() => {
    setupDOM();
  });

  test("renders empty state when hypotheses is null", () => {
    renderHypotheses(null);
    const panel = document.getElementById("hypothesisPanel");
    const badge = document.getElementById("hypothesisBadge");
    expect(panel.innerHTML).toContain("No hypotheses generated yet");
    expect(badge.textContent).toBe("0");
  });

  test("renders empty state when hypotheses is undefined", () => {
    renderHypotheses(undefined);
    const panel = document.getElementById("hypothesisPanel");
    const badge = document.getElementById("hypothesisBadge");
    expect(panel.innerHTML).toContain("No hypotheses generated yet");
    expect(badge.textContent).toBe("0");
  });

  test("renders empty state when hypotheses is an empty array", () => {
    renderHypotheses([]);
    const panel = document.getElementById("hypothesisPanel");
    const badge = document.getElementById("hypothesisBadge");
    expect(panel.innerHTML).toContain("No hypotheses generated yet");
    expect(badge.textContent).toBe("0");
  });

  test("renders a single hypothesis correctly", () => {
    renderHypotheses([
      {
        title: "Test Hypothesis",
        statement: "This is a test statement.",
        rationale: "Because of prior work.",
        novelty: 0.8,
        feasibility: 0.6,
        gap_addressed: "methodology",
        proposed_approach: "Use transformer-based approach",
        evaluation_approach: "A/B testing",
        required_resources: ["GPU", "Dataset X"],
      },
    ]);
    const panel = document.getElementById("hypothesisPanel");
    const badge = document.getElementById("hypothesisBadge");
    expect(badge.textContent).toBe("1");
    expect(panel.innerHTML).toContain("Test Hypothesis");
    expect(panel.innerHTML).toContain("This is a test statement.");
    expect(panel.innerHTML).toContain("Because of prior work.");
    expect(panel.innerHTML).toContain("80%");
    expect(panel.innerHTML).toContain("60%");
    expect(panel.innerHTML).toContain("methodology");
    expect(panel.innerHTML).toContain("Use transformer-based approach");
    expect(panel.innerHTML).toContain("A/B testing");
    expect(panel.innerHTML).toContain("GPU");
    expect(panel.innerHTML).toContain("Dataset X");
  });

  test("renders multiple hypotheses", () => {
    renderHypotheses([
      { title: "Hyp A", statement: "Stmt A", novelty: 0.5, feasibility: 0.5 },
      { title: "Hyp B", statement: "Stmt B", novelty: 0.9, feasibility: 0.3 },
    ]);
    const badge = document.getElementById("hypothesisBadge");
    expect(badge.textContent).toBe("2");
    const panel = document.getElementById("hypothesisPanel");
    expect(panel.innerHTML).toContain("Hyp A");
    expect(panel.innerHTML).toContain("Hyp B");
    expect(panel.innerHTML).toContain("Stmt A");
    expect(panel.innerHTML).toContain("Stmt B");
  });

  test("handles missing optional fields gracefully", () => {
    renderHypotheses([
      {
        title: "Minimal",
        statement: "Just a statement",
      },
    ]);
    const panel = document.getElementById("hypothesisPanel");
    // Should not throw and should render sans optional fields
    expect(panel.innerHTML).toContain("Minimal");
    expect(panel.innerHTML).toContain("Just a statement");
    // Optional fields like rationale, proposed_approach should be absent
    expect(panel.innerHTML).not.toContain("Approach:");
  });

  test("clamps novelty and feasibility scores to 0-100%", () => {
    renderHypotheses([
      {
        title: "Edge",
        statement: "Edge scores",
        novelty: 2.5,
        feasibility: -0.5,
      },
    ]);
    const panel = document.getElementById("hypothesisPanel");
    // 2.5 * 100 = 250 → clamped to 100
    expect(panel.innerHTML).toContain("100%");
    // -0.5 * 100 = -50 → clamped to 0
    expect(panel.innerHTML).not.toContain("-50%");
  });

  test("defaults gap_addressed to 'general' when missing", () => {
    renderHypotheses([
      { title: "No Gap", statement: "No gap field" },
    ]);
    const panel = document.getElementById("hypothesisPanel");
    expect(panel.innerHTML).toContain("general");
  });

  test("defaults title to 'Untitled Hypothesis' when missing", () => {
    renderHypotheses([
      { statement: "No title here" },
    ]);
    const panel = document.getElementById("hypothesisPanel");
    expect(panel.innerHTML).toContain("Untitled Hypothesis");
  });

  test("does nothing if panel element does not exist", () => {
    document.body.innerHTML = ""; // remove panel
    expect(() => {
      renderHypotheses([{ title: "A", statement: "B" }]);
    }).not.toThrow();
  });
});

describe("renderStrategy", () => {
  beforeEach(() => {
    setupDOM();
  });

  test("renders empty state when strategy is null", () => {
    renderStrategy(null);
    const panel = document.getElementById("strategyPanel");
    const badge = document.getElementById("strategyBadge");
    expect(panel.innerHTML).toContain("No strategy recommendations yet.");
    expect(badge.textContent).toBe("Ready");
  });

  test("renders empty state when strategy is undefined", () => {
    renderStrategy(undefined);
    const panel = document.getElementById("strategyPanel");
    expect(panel.innerHTML).toContain("No strategy recommendations yet.");
  });

  test("renders empty state when strategy has no methodology", () => {
    renderStrategy({ datasets: {} });
    const panel = document.getElementById("strategyPanel");
    expect(panel.innerHTML).toContain("No strategy recommendations yet.");
  });

  test("renders methodology approaches correctly", () => {
    renderStrategy({
      methodology: {
        recommended_approaches: [
          {
            name: "Approach A",
            description: "Description A",
            rationale: "Rationale A",
          },
          {
            name: "Approach B",
            description: "Description B",
          },
        ],
      },
    });
    const panel = document.getElementById("strategyPanel");
    const badge = document.getElementById("strategyBadge");
    expect(badge.textContent).toBe("Ready");
    expect(panel.innerHTML).toContain("Methodology");
    expect(panel.innerHTML).toContain("Approach A");
    expect(panel.innerHTML).toContain("Description A");
    expect(panel.innerHTML).toContain("Rationale A");
    expect(panel.innerHTML).toContain("Approach B");
    expect(panel.innerHTML).toContain("Description B");
  });

  test("renders avoid chips when present", () => {
    renderStrategy({
      methodology: {
        recommended_approaches: [{ name: "A", description: "D" }],
        avoid: ["Old method X", "Naive baseline Y"],
      },
    });
    const panel = document.getElementById("strategyPanel");
    expect(panel.innerHTML).toContain("Avoid");
    expect(panel.innerHTML).toContain("Old method X");
    expect(panel.innerHTML).toContain("Naive baseline Y");
  });

  test("does not render avoid section when avoid list is empty", () => {
    renderStrategy({
      methodology: {
        recommended_approaches: [{ name: "A", description: "D" }],
        avoid: [],
      },
    });
    const panel = document.getElementById("strategyPanel");
    expect(panel.innerHTML).not.toContain("p26-avoid-chip");
  });

  test("renders datasets section when present", () => {
    renderStrategy({
      methodology: {
        recommended_approaches: [{ name: "A", description: "D" }],
      },
      datasets: {
        recommended: [
          { name: "DS1", description: "Dataset one" },
          { name: "DS2", description: "Dataset two" },
        ],
      },
    });
    const panel = document.getElementById("strategyPanel");
    expect(panel.innerHTML).toContain("Datasets");
    expect(panel.innerHTML).toContain("DS1");
    expect(panel.innerHTML).toContain("Dataset one");
    expect(panel.innerHTML).toContain("DS2");
    expect(panel.innerHTML).toContain("Dataset two");
  });

  test("renders baselines section when present", () => {
    renderStrategy({
      methodology: {
        recommended_approaches: [{ name: "A", description: "D" }],
      },
      baselines: {
        recommended: [{ name: "BL1", description: "Baseline one" }],
      },
    });
    const panel = document.getElementById("strategyPanel");
    expect(panel.innerHTML).toContain("Baselines");
    expect(panel.innerHTML).toContain("BL1");
    expect(panel.innerHTML).toContain("Baseline one");
  });

  test("renders evaluation metrics and ablation", () => {
    renderStrategy({
      methodology: {
        recommended_approaches: [{ name: "A", description: "D" }],
      },
      evaluation: {
        primary_metrics: ["Accuracy", "F1", "Latency"],
        ablation: "Remove attention layer; Remove skip connections",
      },
    });
    const panel = document.getElementById("strategyPanel");
    expect(panel.innerHTML).toContain("Evaluation");
    expect(panel.innerHTML).toContain("Accuracy");
    expect(panel.innerHTML).toContain("F1");
    expect(panel.innerHTML).toContain("Latency");
    expect(panel.innerHTML).toContain("Ablation");
    expect(panel.innerHTML).toContain("Remove attention layer");
  });

  test("handles evaluation ablation as array", () => {
    renderStrategy({
      methodology: {
        recommended_approaches: [{ name: "A", description: "D" }],
      },
      evaluation: {
        primary_metrics: ["F1"],
        ablation: ["Remove A", "Remove B", "Remove C"],
      },
    });
    const panel = document.getElementById("strategyPanel");
    expect(panel.innerHTML).toContain("Remove A; Remove B; Remove C");
  });

  test("does nothing if panel element does not exist", () => {
    document.body.innerHTML = "";
    expect(() => {
      renderStrategy({ methodology: { recommended_approaches: [] } });
    }).not.toThrow();
  });
});

describe("renderGapExploration", () => {
  beforeEach(() => {
    setupDOM();
  });

  test("does nothing when gapExp is null", () => {
    renderGapExploration(null);
    const panel = document.getElementById("hypothesisPanel");
    expect(panel.innerHTML).toBe("");
  });

  test("does nothing when gapExp is undefined", () => {
    renderGapExploration(undefined);
    const panel = document.getElementById("hypothesisPanel");
    expect(panel.innerHTML).toBe("");
  });

  test("does nothing when is_thin is false", () => {
    renderGapExploration({ is_thin: false, analysis: "Some analysis" });
    const panel = document.getElementById("hypothesisPanel");
    expect(panel.innerHTML).toBe("");
  });

  test("does nothing when is_thin is missing", () => {
    renderGapExploration({ analysis: "Some analysis" });
    const panel = document.getElementById("hypothesisPanel");
    expect(panel.innerHTML).toBe("");
  });

  test("prepends thin note when is_thin is true", () => {
    // Put some existing content in the panel
    const panel = document.getElementById("hypothesisPanel");
    panel.innerHTML = "<p>Existing content</p>";

    renderGapExploration({
      is_thin: true,
      analysis: "Very few papers on this specific angle.",
      alternative_queries: ["query A", "query B"],
      recommendation: "broaden_search_terms",
    });

    // The thin note should be prepended
    expect(panel.innerHTML).toContain("Thin Literature Detected");
    expect(panel.innerHTML).toContain("Very few papers on this specific angle.");
    expect(panel.innerHTML).toContain("query A");
    expect(panel.innerHTML).toContain("query B");
    expect(panel.innerHTML).toContain("broaden search terms");
    // Existing content should still be there (note was prepended)
    expect(panel.innerHTML).toContain("Existing content");
    // The thin note should be first
    const firstChild = panel.firstChild;
    expect(firstChild.className).toContain("p26-thin-note");
  });

  test("handles missing optional fields in gapExp", () => {
    renderGapExploration({
      is_thin: true,
    });
    const panel = document.getElementById("hypothesisPanel");
    expect(panel.innerHTML).toContain("Thin Literature Detected");
    // Should handle missing analysis, alternative_queries, recommendation gracefully
    expect(panel.querySelector(".p26-thin-note")).not.toBeNull();
  });

  test("does nothing if hypothesisPanel does not exist", () => {
    document.body.innerHTML = "";
    expect(() => {
      renderGapExploration({ is_thin: true, analysis: "test" });
    }).not.toThrow();
  });
});
