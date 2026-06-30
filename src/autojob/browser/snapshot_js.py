"""JS iniettato nella pagina per costruire lo snapshot indicizzato (piano §2).

Raccoglie SOLO gli elementi interattivi (+ label), attraversando open shadow DOM e
iframe same-origin; tagga ogni elemento con ``data-aj-index`` per le azioni successive.
Ritorna un oggetto serializzabile (url, title, viewport, dom_hash, elements, forms, frames).
"""

from __future__ import annotations

SNAPSHOT_JS = r"""
() => {
  const out = [];
  const forms = [];
  const frames = [];
  let idx = 0;

  const winOf = (el) => (el.ownerDocument && el.ownerDocument.defaultView) || window;
  const isVisible = (el) => {
    try {
      const r = el.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) return false;
      const st = winOf(el).getComputedStyle(el);
      return st && st.visibility !== 'hidden' && st.display !== 'none' && st.opacity !== '0';
    } catch (e) { return false; }
  };
  const inViewport = (r) => r.bottom > 0 && r.right > 0 && r.top < (window.innerHeight || 0) && r.left < (window.innerWidth || 0);

  const labelText = (el) => {
    const aria = el.getAttribute && el.getAttribute('aria-label');
    if (aria && aria.trim()) return aria.trim();
    const lb = el.getAttribute && el.getAttribute('aria-labelledby');
    if (lb) {
      const t = lb.split(/\s+/).map((id) => { const n = el.ownerDocument.getElementById(id); return n ? n.textContent : ''; }).join(' ').trim();
      if (t) return t;
    }
    if (el.id) {
      try {
        const lab = el.ownerDocument.querySelector('label[for="' + CSS.escape(el.id) + '"]');
        if (lab && lab.textContent.trim()) return lab.textContent.trim();
      } catch (e) {}
    }
    const wrap = el.closest && el.closest('label');
    if (wrap && wrap.textContent.trim()) return wrap.textContent.trim();
    const ph = el.getAttribute && el.getAttribute('placeholder');
    if (ph && ph.trim()) return ph.trim();
    const title = el.getAttribute && el.getAttribute('title');
    if (title && title.trim()) return title.trim();
    return null;
  };

  const roleOf = (el) => {
    const r = el.getAttribute && el.getAttribute('role');
    if (r) return r;
    const tag = el.tagName.toLowerCase();
    if (tag === 'a') return 'link';
    if (tag === 'button') return 'button';
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'input') {
      const t = (el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      if (t === 'file') return 'file';
      if (t === 'submit' || t === 'button') return 'button';
      return 'textbox';
    }
    return tag;
  };

  const isInteractive = (el) => {
    const tag = el.tagName ? el.tagName.toLowerCase() : '';
    if (['input', 'select', 'textarea', 'button'].includes(tag)) return true;
    if (tag === 'a' && el.hasAttribute('href')) return true;
    if (el.hasAttribute && el.hasAttribute('role')) {
      const r = el.getAttribute('role');
      if (['button', 'link', 'checkbox', 'radio', 'combobox', 'textbox', 'menuitem', 'tab', 'switch'].includes(r)) return true;
    }
    if (el.hasAttribute && el.hasAttribute('contenteditable') && el.getAttribute('contenteditable') !== 'false') return true;
    if (el.hasAttribute && el.hasAttribute('tabindex')) return true;
    return false;
  };

  const groupId = (el) => {
    const f = el.closest && (el.closest('form') || el.closest('fieldset') || el.closest('[role="group"]'));
    if (!f) return null;
    return f.id || (f.getAttribute && f.getAttribute('name')) || ('group@' + f.tagName.toLowerCase());
  };

  const collect = (root, framePath) => {
    let nodes;
    try { nodes = root.querySelectorAll('*'); } catch (e) { return; }
    for (const el of nodes) {
      if (el.shadowRoot) collect(el.shadowRoot, framePath);
      if (el.tagName && el.tagName.toLowerCase() === 'iframe') {
        let doc = null;
        const src = (el.getAttribute && el.getAttribute('src')) || '';
        try { doc = el.contentDocument; } catch (e) { doc = null; }
        if (doc) { frames.push({ frame_path: framePath.concat([src || 'iframe']), url: src, cross_origin: false }); collect(doc, framePath.concat([src || 'iframe'])); }
        else { frames.push({ frame_path: framePath.concat([src || 'iframe']), url: src, cross_origin: true }); }
        continue;
      }
      if (!isInteractive(el) || !isVisible(el)) continue;
      const r = el.getBoundingClientRect();
      const tag = el.tagName.toLowerCase();
      let options = null;
      if (tag === 'select') {
        options = Array.from(el.options).map((o) => ({ value: o.value, label: o.label || o.textContent, selected: o.selected }));
      }
      try { el.setAttribute('data-aj-index', String(idx)); } catch (e) {}
      out.push({
        index: idx,
        handle: '[data-aj-index="' + idx + '"]',
        role: roleOf(el),
        tag: tag,
        type: el.getAttribute ? el.getAttribute('type') : null,
        label: labelText(el),
        text: (tag === 'button' || tag === 'a') ? (el.textContent || '').trim().slice(0, 120) : null,
        value: ('value' in el) ? (el.value == null ? null : String(el.value)) : null,
        placeholder: el.getAttribute ? el.getAttribute('placeholder') : null,
        options: options,
        checked: ('checked' in el) ? !!el.checked : null,
        required: el.hasAttribute ? el.hasAttribute('required') : false,
        enabled: !el.disabled,
        visible: true,
        focused: el.ownerDocument.activeElement === el,
        in_viewport: inViewport(r),
        bbox: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
        autocomplete: el.getAttribute ? el.getAttribute('autocomplete') : null,
        group_id: groupId(el),
        frame_path: framePath,
        attrs: { name: (el.getAttribute && el.getAttribute('name')) || null, id: el.id || null, href: (tag === 'a' ? el.href : null) }
      });
      idx++;
    }
  };

  collect(document, []);

  for (const f of Array.from(document.querySelectorAll('form'))) {
    const gid = f.id || (f.getAttribute('name')) || 'group@form';
    forms.push({
      group_id: gid,
      action: f.getAttribute('action'),
      method: (f.getAttribute('method') || 'get'),
      field_indexes: out.filter((n) => n.group_id === gid).map((n) => n.index)
    });
  }

  let has_captcha = false;
  try { has_captcha = /recaptcha|hcaptcha|turnstile|g-recaptcha|cf-challenge/i.test(document.documentElement.outerHTML); } catch (e) {}

  let h = 0;
  const sig = out.map((n) => n.tag + (n.role || '') + (n.label || '')).join('|') + '#' + out.length;
  for (let i = 0; i < sig.length; i++) { h = (h * 31 + sig.charCodeAt(i)) >>> 0; }

  return {
    url: location.href,
    title: document.title,
    viewport: { w: window.innerWidth, h: window.innerHeight, scroll_x: window.scrollX, scroll_y: window.scrollY },
    dom_hash: String(h),
    elements: out,
    forms: forms,
    frames: frames,
    has_captcha_hint: has_captcha
  };
}
"""
