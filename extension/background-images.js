/*
 * dhriti-e1 · background-images.js — plumbing for the Images exile (D-082)
 *
 * [PLUG-IN] This is a MERGE-IN fragment for your existing E1 service worker,
 * not a standalone worker. Two responsibilities:
 *
 *  1. Observation: webRequest.onErrorOccurred is observational-only, which is
 *     legal in MV3. DNR-blocked Images requests surface here and are forwarded
 *     to the bridge as content-blind events (host + pattern flag; the query
 *     string is stripped — L-4).
 *  2. Parking: relays the wall card's "Park this urge" to POST /session/park.
 *
 * [PLUG-IN] If your ledger events go through the native host instead of the
 * loopback bridge, replace bridgePost() with your chrome.runtime.sendNativeMessage
 * call — the payload shape is the same.
 */

// [PLUG-IN] match your bridge config: loopback origin + the storage key that
// holds the X-Dhriti-Token minted at first-run pairing.
const BRIDGE = {
  origin: 'http://127.0.0.1:8791',
  tokenKey: 'bridgeToken',
};

// Mirror of host_permissions — keep in sync (manifest-additions.json).
const URL_FILTERS = [
  '*://*.google.com/*',
  '*://*.google.co.in/*',
  '*://*.google.co.uk/*',
  '*://*.google.ca/*',
  '*://*.google.com.au/*',
  '*://*.google.de/*',
  '*://*.google.fr/*',
  '*://*.gstatic.com/*',
];

// Images entry points, URL-level. Everything that matches is reported.
const IMG_RX = /(?:images|lens)\.google\.[a-z.]+|google\.[a-z.]+\/(?:imghp|imgres)|(?:^|[&?])(?:tbm=isch|udm=2)(?:[&#]|$)/i;

async function bridgePost(path, payload) {
  try {
    const stored = await chrome.storage.local.get(BRIDGE.tokenKey);
    const token = stored[BRIDGE.tokenKey];
    if (!token) return; // bridge not paired yet: fail-safe TTL behavior, stay silent
    await fetch(BRIDGE.origin + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Dhriti-Token': token },
      body: JSON.stringify(payload),
    });
  } catch (_) {
    /* bridge down: observation lapses, enforcement (rings 1+2) is unaffected */
  }
}

// Ring-2 hits: DNR aborts the request, onErrorOccurred reports it.
chrome.webRequest.onErrorOccurred.addListener((details) => {
  if (!IMG_RX.test(details.url)) return;
  let host = '';
  try { host = new URL(details.url).hostname; } catch (_) {}
  bridgePost('/session/event', {
    code: 'vertical_block',
    target: 'images-vertical',
    host,                 // hostname only — query text deliberately dropped (L-4)
    stage: 'navigate',    // kill-chain stage attribution
  });
}, { urls: URL_FILTERS });

// Wall card + sweep events from the content script.
chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (!msg || typeof msg.type !== 'string') return false;

  if (msg.type === 'dhriti/park') {
    bridgePost('/session/park', {
      kind: 'vertical-wall',
      sparked_by: msg.sparkedBy || 'images-vertical',
    });
    reply({ ok: true });
    return false;
  }

  if (msg.type === 'dhriti/event') {
    bridgePost('/session/event', {
      code: msg.code || 'unknown',
      target: msg.target || 'images-vertical',
      stage: msg.stage || 'unknown',
      count: typeof msg.count === 'number' ? msg.count : undefined,
    });
    reply({ ok: true });
    return false;
  }

  return false;
});
