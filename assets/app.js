(function () {
  // --- Analytics helper ---
  function track(eventName, params) {
    if (typeof window.gtag !== 'function') return;
    var payload = {};
    if (params) {
      for (var k in params) {
        if (Object.prototype.hasOwnProperty.call(params, k)) payload[k] = params[k];
      }
    }
    if (window.REP_NAME && !payload.rep_name) payload.rep_name = window.REP_NAME;
    window.gtag('event', eventName, payload);
  }

  // --- Click-to-copy with visual feedback ---
  function copyToClipboard(text, btn) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { flashCopied(btn); },
        function () { fallback(text, btn); }
      );
    } else {
      fallback(text, btn);
    }
  }
  function fallback(text, btn) {
    var ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.left = "-9999px";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); flashCopied(btn); } catch (e) {}
    document.body.removeChild(ta);
  }
  function flashCopied(btn) {
    var orig = btn.innerHTML;
    btn.classList.add("copied");
    btn.innerHTML = '<span class="ico">✓</span> Copied';
    setTimeout(function () {
      btn.classList.remove("copied");
      btn.innerHTML = orig;
    }, 1400);
  }

  document.addEventListener("click", function (e) {
    // Copy buttons
    var copyBtn = e.target.closest("[data-copy]");
    if (copyBtn) {
      e.preventDefault();
      copyToClipboard(copyBtn.getAttribute("data-copy"), copyBtn);
      var label = (copyBtn.textContent || "").trim().toLowerCase();
      var variant = label.indexOf("email") !== -1 ? "email_body" : "text_blurb";
      track("review_copy", { copy_variant: variant });
      return;
    }
    // SMS / mailto action buttons
    var linkBtn = e.target.closest("a.btn");
    if (linkBtn) {
      var href = linkBtn.getAttribute("href") || "";
      if (href.indexOf("sms:") === 0) {
        track("review_text_send", { channel: "sms" });
      } else if (href.indexOf("mailto:") === 0) {
        track("review_email_send", { channel: "mailto" });
      }
      return;
    }
    // Rep cards on index page
    var card = e.target.closest("a.rep-card");
    if (card) {
      var nameEl = card.querySelector(".rep-name");
      var rn = nameEl ? nameEl.textContent.trim() : null;
      if (rn) track("rep_card_click", { rep_name: rn });
    }
  });

  // --- Scenario filter pills ---
  var pills = document.querySelectorAll(".pill[data-scenario]");
  var cards = document.querySelectorAll(".review[data-scenarios]");
  function applyFilter(scenario) {
    pills.forEach(function (p) {
      p.classList.toggle("active", p.dataset.scenario === scenario);
    });
    var visible = 0;
    cards.forEach(function (c) {
      var show;
      if (scenario === "all") {
        show = true;
      } else if (scenario === "__named__") {
        show = c.dataset.named === "1";
      } else {
        var s = (c.dataset.scenarios || "").split("|");
        show = s.indexOf(scenario) !== -1;
      }
      c.style.display = show ? "" : "none";
      if (show) visible++;
    });
    var empty = document.getElementById("empty-state");
    if (empty) empty.style.display = visible === 0 ? "" : "none";
  }
  pills.forEach(function (p) {
    p.addEventListener("click", function () {
      applyFilter(p.dataset.scenario);
      track("scenario_filter", { scenario: p.dataset.scenario });
    });
  });
})();
