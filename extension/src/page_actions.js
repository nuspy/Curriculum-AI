// Funzioni eseguite nel MAIN world della pagina (native setter + dispatch → compatibili React/Vue).
// Operano per data-aj-index assegnato dallo snapshot.

export function getPageText() {
  return document.body ? document.body.innerText : "";
}

export function detectCaptchaInPage() {
  try {
    const has = /recaptcha|hcaptcha|turnstile|g-recaptcha|cf-challenge/i.test(document.documentElement.outerHTML);
    return { present: has, kind: "unknown", url: location.href };
  } catch (e) {
    return { present: false };
  }
}

export function extractIdentity() {
  const meta = (n) => { const m = document.querySelector(n); return m ? m.content : null; };
  return { url: location.href, title: document.title, og_title: meta('meta[property="og:title"]') };
}

export function actOnIndex(op, index, value) {
  const el = document.querySelector('[data-aj-index="' + index + '"]');
  if (!el) return { ok: false, index: index, error_kind: "not_found" };
  try {
    if (op === "click") { el.click(); return { ok: true, index: index, dom_changed: true }; }
    if (op === "fill") {
      const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
      setter.call(el, value);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      el.dispatchEvent(new Event("blur", { bubbles: true }));
      return { ok: true, index: index, value_after: el.value, dom_changed: true };
    }
    if (op === "checkbox") {
      if (el.checked !== !!value) el.click();
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return { ok: true, index: index, value_after: String(el.checked) };
    }
    if (op === "select") {
      if (value != null) el.value = value;
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return { ok: true, index: index, value_after: el.value };
    }
    if (op === "scroll") { el.scrollIntoView({ block: "center", inline: "center" }); return { ok: true, index: index }; }
    if (op === "key") {
      el.dispatchEvent(new KeyboardEvent("keydown", { key: value, bubbles: true }));
      el.dispatchEvent(new KeyboardEvent("keyup", { key: value, bubbles: true }));
      return { ok: true, index: index };
    }
  } catch (e) {
    return { ok: false, index: index, error_kind: "not_interactable", message: String(e).slice(0, 200) };
  }
  return { ok: false, index: index, error_kind: "unsupported_op" };
}
