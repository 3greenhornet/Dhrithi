/**
 * Dhriti Wall — configuration.
 *
 * MANUAL STEP (the only one): after `dhriti init`, copy the token from
 * <dhriti-home>/bridge_token below (or set via chrome.storage.local).
 * Then load this folder unpacked:
 * chrome://extensions -> Developer mode -> Load unpacked.
 *
 * The extension has no options page, no popup, no badges with counts,
 * no gamification. The wall does not respond. (Wall Principle)
 */

const CONFIG = {
  // The daemon's local bridge. Default matches dhriti.config.json.
  bridgeUrl: "http://127.0.0.1:7311",
  // Bridge token from ~/.dhriti/bridge_token:
  bridgeToken: "PASTE_BRIDGE_TOKEN_HERE",
  // Poll the daemon this often (seconds).
  pollSeconds: 30,
};

// Fail-safe: if the daemon dies mid-window, the cached policy keeps
// enforcing until its expires_at (served by the daemon with a TTL).
// Outside a bootcamp/window the daemon serves enforce=false and the
// extension stays dormant. No policy -> no blocking. Ever.

self.DHRITI_CONFIG = CONFIG;
