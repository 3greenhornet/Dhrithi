// blocked.js — renders the user's own contract line on the wall page.
// Reads the cached policy from local storage. If the daemon has not
// been seen yet, shows a neutral placeholder. No messages, no tips.
//
// Wall Silence Protocol (v0.7.0 §4.12): the line is hidden until the
// small dot in the corner is clicked. The count line (§3.9) is a
// single line of fact when the mirror is enabled — not a link, not a
// button, not a form (L-1), a plain number, not a nudge (L-2/L-7).

(function () {
  chrome.storage.local.get("cachedPolicy", (stored) => {
    const policy = stored.cachedPolicy || {};
    const line = document.getElementById("line");
    const count = document.getElementById("count");

    // the line content (revealed only via the dot)
    if (policy.contract_line) {
      line.textContent = policy.contract_line; // the user's own words
    } else if (policy.enforce) {
      line.textContent = "The window is open.";
    } else {
      line.textContent = "Dhriti is dormant (no active day).";
    }

    // the count line: shown when the mirror is enabled and the count
    // is a fact. Not clickable. Not styled like a notification.
    if (policy.mirror_unopened_count !== null &&
        policy.mirror_unopened_count !== undefined) {
      count.textContent = policy.mirror_unopened_count +
        " saved item(s) are unopened.";
      count.hidden = false;
    }

    // §3.13: the emergency contacts (declared cold), small text,
    // only when a break is initiated during an active session.
    // A fact on the wall, not a notification.
    const contacts = document.getElementById("contacts");
    if (Array.isArray(policy.emergency_contacts) &&
        policy.emergency_contacts.length > 0) {
      contacts.textContent = "while you sit with this: " +
        policy.emergency_contacts
          .map((c) => c.label + " (" + c.contact + ")")
          .join(", ");
      contacts.hidden = false;
    }

    // reveal on the dot click; clicking again hides it again
    const dot = document.getElementById("reveal-dot");
    dot.addEventListener("click", () => {
      line.hidden = !line.hidden;
    });
  });
})();
