const stEl = document.getElementById("st");
const detail = document.getElementById("detail");
const fillBtn = document.getElementById("fill");
const fillRes = document.getElementById("fillres");

function renderFill(a) {
  if (!a) { fillRes.textContent = ""; return; }
  if (a.pending) { fillRes.textContent = "⏳ compilazione in corso…"; return; }
  if (a.ok === false) { fillRes.textContent = "errore: " + (a.error || "?"); return; }
  const nu = (a.needs_user || []).length;
  const er = (a.errors || []).length;
  fillRes.textContent = "✅ compilati " + (a.filled_count ?? 0) + " campi"
    + (nu ? " · " + nu + " da completare a mano" : "")
    + (er ? " · " + er + " errori" : "");
}

function render(s) {
  if (!s) {
    stEl.className = "bad"; stEl.textContent = "🔴 service worker non attivo";
    detail.textContent = "Ricarica l'estensione in opera://extensions"; fillBtn.disabled = true; return;
  }
  if (!s.hasToken) {
    stEl.className = "warn"; stEl.textContent = "⚠️ token mancante";
    detail.textContent = "Apri Opzioni, incolla il token e premi Salva."; fillBtn.disabled = true; return;
  }
  if (s.connected) {
    stEl.className = "ok"; stEl.textContent = "🟢 connesso al daemon";
    detail.textContent = s.url || ""; fillBtn.disabled = false;
  } else {
    stEl.className = "bad"; stEl.textContent = "🔴 non connesso";
    detail.textContent = (s.lastError || "in attesa…") + (s.url ? "  ·  " + s.url : ""); fillBtn.disabled = true;
  }
  renderFill(s.lastAutofill);
}

function refresh() {
  try {
    chrome.runtime.sendMessage({ type: "status" }, (resp) => {
      if (chrome.runtime.lastError) { render(null); return; }
      render(resp);
    });
  } catch (e) { render(null); }
}

fillBtn.addEventListener("click", () => {
  fillRes.textContent = "⏳ compilazione avviata… (guarda il form nella pagina)";
  chrome.runtime.sendMessage({ type: "autofill" }, () => setTimeout(refresh, 600));
});
document.getElementById("reconnect").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "reconnect" }, () => setTimeout(refresh, 800));
});
document.getElementById("opt").addEventListener("click", () => chrome.runtime.openOptionsPage());

refresh();
setInterval(refresh, 1500);
