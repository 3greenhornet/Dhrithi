(() => {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const query = params.get("query") || "Unknown query";
  const target = params.get("target") || "Declared Placement Preparation";
  const score = params.get("score") || "0";
  const originalUrl = params.get("orig_url") || "";

  document.getElementById("held-query").textContent = `"${query}"`;
  document.getElementById("active-target").textContent = target;
  document.getElementById("match-score").textContent = `${Math.round(parseFloat(score) * 100)}%`;

  // 1. Back to Target
  document.getElementById("btn-back").addEventListener("click", () => {
    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.close();
    }
  });

  // 2. Park for 20:00
  document.getElementById("btn-park").addEventListener("click", () => {
    const btn = document.getElementById("btn-park");
    btn.textContent = "Saving to Parking Lot...";
    btn.disabled = true;

    chrome.runtime.sendMessage({ type: "quick_park", text: query }, (resp) => {
      btn.textContent = "✓ Parked for 20:00 Review";
      setTimeout(() => {
        if (window.history.length > 1) {
          window.history.back();
        } else {
          window.close();
        }
      }, 900);
    });
  });

  // 3. Declare Pivot (30s Deliberate Pause)
  const timerBox = document.getElementById("timer-box");
  const timerCount = document.getElementById("timer-count");
  const confirmBtn = document.getElementById("btn-confirm-pivot");
  const pivotBtn = document.getElementById("btn-pivot");

  let remaining = 30;
  let interval = null;

  pivotBtn.addEventListener("click", () => {
    pivotBtn.style.display = "none";
    timerBox.style.display = "block";

    interval = setInterval(() => {
      remaining -= 1;
      timerCount.textContent = `${remaining}s`;
      if (remaining <= 0) {
        clearInterval(interval);
        timerCount.style.display = "none";
        confirmBtn.style.display = "block";
      }
    }, 1000);
  });

  confirmBtn.addEventListener("click", () => {
    confirmBtn.textContent = "Learning Topic Anchor...";
    confirmBtn.disabled = true;

    chrome.runtime.sendMessage({ type: "learn_safe_anchor", anchor: query }, (resp) => {
      if (originalUrl) {
        window.location.href = originalUrl;
      } else {
        window.history.back();
      }
    });
  });
})();
