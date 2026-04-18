
(function () {
  // --- Click-to-copy with visual feedback ---
  function copyToClipboard(text, btn) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        () => flashCopied(btn),
        () => fallback(text, btn)
      );
    } else {
      fallback(text, btn);
    }
  }
  function fallback(text, btn) {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.left = "-9999px";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); flashCopied(btn); } catch (e) {}
    document.body.removeChild(ta);
  }
  function flashCopied(btn) {
    const orig = btn.innerHTML;
    btn.classList.add("copied");
    btn.innerHTML = '<span class="ico">✓</span> Copied';
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.innerHTML = orig;
    }, 1400);
  }
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    e.preventDefault();
    copyToClipboard(btn.getAttribute("data-copy"), btn);
  });

  // --- Scenario filter pills ---
  const pills = document.querySelectorAll(".pill[data-scenario]");
  const cards = document.querySelectorAll(".review[data-scenarios]");
  function applyFilter(scenario) {
    pills.forEach((p) => p.classList.toggle("active", p.dataset.scenario === scenario));
    let visible = 0;
    cards.forEach((c) => {
      let show;
      if (scenario === "all") {
        show = true;
      } else if (scenario === "__named__") {
        show = c.dataset.named === "1";
      } else {
        const s = (c.dataset.scenarios || "").split("|");
        show = s.indexOf(scenario) !== -1;
      }
      c.style.display = show ? "" : "none";
      if (show) visible++;
    });
    const empty = document.getElementById("empty-state");
    if (empty) empty.style.display = visible === 0 ? "" : "none";
  }
  pills.forEach((p) => {
    p.addEventListener("click", () => applyFilter(p.dataset.scenario));
  });
})();
