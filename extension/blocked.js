// blocked.js — renders the user's own contract line on the wall page.
// Reads the cached policy from local storage. If the daemon has not
// been seen yet, shows a neutral placeholder. No messages, no tips.

chrome.storage.local.get("cachedPolicy", (stored) => {
  const policy = stored.cachedPolicy || {};
  const el = document.getElementById("line");
  if (policy.contract_line) {
    el.textContent = policy.contract_line; // the user's own words
  } else if (policy.enforce) {
    el.textContent = "The window is open.";
  } else {
    el.textContent = "Dhriti is dormant (no active day).";
  }
});
