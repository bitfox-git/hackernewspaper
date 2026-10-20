"""Get cookie/consent banners out of the way before a screenshot.

First try to click a button of a known consent manager or with a consent-like text,
preferring "reject"/"necessary only" over "accept", in the page and its iframes
(Sourcepoint, Quantcast and others render in an iframe). Whatever is left of a fixed or
sticky consent overlay is hidden with CSS.
"""

import logging

log = logging.getLogger("hackernewspaper")

# buttons of common consent managers, reject variants first
KNOWN_BUTTONS = [
    "#onetrust-reject-all-handler",
    "#CybotCookiebotDialogBodyButtonDecline",
    "#didomi-notice-disagree-button",
    ".fc-cta-do-not-consent",
    ".qc-cmp2-summary-buttons button[mode='secondary']",
    "button.sp_choice_type_REJECT_ALL",
    "#onetrust-accept-btn-handler",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#didomi-notice-agree-button",
    ".fc-cta-consent",
    "button.sp_choice_type_11",
]

# runs in a frame: click the best visible consent-like button, return its text or null
# every element of the document including those in (open) shadow roots, some consent
# managers (e.g. WPConsent) render their banner in one
DEEP_ALL = r"""
  const deepAll = (selector, root = document, out = []) => {
    for (const el of root.querySelectorAll("*")) {
      if (el.matches(selector)) out.push(el);
      if (el.shadowRoot) deepAll(selector, el.shadowRoot, out);
    }
    return out;
  };
  // parent, crossing from a shadow root to its host
  const up = n => n.parentElement || (n.getRootNode() instanceof ShadowRoot ? n.getRootNode().host : null);
"""

CLICK_BY_TEXT = (
    r"""
() => {"""
    + DEEP_ALL
    + r"""
  const reject = /^(reject( all| non-essential( cookies)?| optional( cookies)?| cookies)?|decline( all| cookies)?|deny( all)?|refuse( all)?|disagree|dismiss|(use )?(only )?(strictly )?necessary( cookies)?( only)?|essential( cookies)?( only)?|no,? thanks|opt[ -]out|continue without (accepting|agreeing))$/i;
  const accept = /^(accept( all| all cookies| cookies)?|allow( all| all cookies| cookies)?|agree( and close| & close)?|i agree|i accept|got it|ok(ay)?|consent|understood|close)$/i;
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
  };
  const candidates = deepAll("button, a, [role=button], input[type=button], input[type=submit]")
    .filter(visible)
    .map(el => [el, (el.innerText || el.value || el.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ")])
    .filter(([el, text]) => text.length > 0 && text.length < 40);
  // only buttons inside something that talks about cookies/consent/privacy
  const inConsent = el => {
    for (let n = el; n && n !== document.body; n = up(n)) {
      if (/cookie|consent|gdpr|privacy|cmp/i.test((n.id || "") + " " + (n.className || "") + " " + (n.getAttribute("aria-label") || "")))
        return true;
      if (/cookie|consent|privacy/i.test(n.innerText || "") && (n.innerText || "").length < 3000)
        return true;
    }
    return false;
  };
  const pick = candidates.find(([el, t]) => reject.test(t) && inConsent(el))
            || candidates.find(([el, t]) => accept.test(t) && inConsent(el));
  if (!pick) return null;
  pick[0].click();
  return pick[1];
}
"""
)

# hide what is left: fixed/sticky elements that look like a consent banner, and undo scroll locks
HIDE_OVERLAYS = (
    r"""
() => {"""
    + DEEP_ALL
    + r"""
  let hidden = 0;
  for (const el of deepAll("*")) {
    const s = getComputedStyle(el);
    if (s.position !== "fixed" && s.position !== "sticky") continue;
    const label = (el.id || "") + " " + (typeof el.className === "string" ? el.className : "");
    const text = (el.innerText || "").slice(0, 2000);
    if (/cookie|consent|gdpr|cmp|onetrust|didomi|cookiebot|privacy|sp_message/i.test(label)
        || (/cookie|consent/i.test(text) && /accept|reject|agree|allow|decline|preferences|settings/i.test(text)
            && text.length < 2000)) {
      el.style.setProperty("display", "none", "important");
      hidden++;
    }
  }
  for (const el of [document.documentElement, document.body]) {
    el.style.setProperty("overflow", "auto", "important");
    el.style.removeProperty("position");
  }
  return hidden;
}
"""
)


def dismiss(page, url=""):
    """Best effort, never raises. Returns a short description of what was done."""
    done = []
    try:
        for selector in KNOWN_BUTTONS:
            for frame in page.frames:
                try:
                    button = frame.locator(selector).first
                    if button.count() and button.is_visible():
                        button.click(timeout=2000)
                        done.append(f"clicked {selector}")
                        raise StopIteration
                except StopIteration:
                    raise
                except Exception:
                    pass
        for frame in page.frames:
            try:
                text = frame.evaluate(CLICK_BY_TEXT)
            except Exception:
                continue
            if text:
                done.append(f"clicked '{text}'")
                break
    except StopIteration:
        pass
    if done:
        page.wait_for_timeout(800)
    try:
        hidden = page.evaluate(HIDE_OVERLAYS)
        if hidden:
            done.append(f"hid {hidden} overlay(s)")
    except Exception:
        pass
    if done:
        log.info("Consent on %s: %s", url, ", ".join(done))
    return ", ".join(done)
