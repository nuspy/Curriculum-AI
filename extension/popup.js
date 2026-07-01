const stEl = document.getElementById("st");
const detail = document.getElementById("detail");

function render(s) {
  if (!s) {
    stEl.className = "bad";
    stEl.textContent = "🔴 service worker non attivo";
    detail.textContent = "Ricarica l'estensione in opera://extensions";
    return;
  }
  if (!s.hasToken) {
    stEl.className = "warn";
    stEl.textContent = "⚠️ token mancante";
    detail.textContent = "Apri Opzioni, incolla il token e premi Salva.";
    return;
  }
  if (s.connected) {
    stEl.className = "ok";
    stEl.textContent = "🟢 connesso al daemon";
    detail.textContent = s.url || "";
    return;
  }
  stEl.className = "bad";
  stEl.textContent = "🔴 non connesso";
  detail.textContent = (s.lastError || "in attesa…") + (s.url ? "  ·  " + s.url : "");
}

function refresh() {
  try {
    chrome.runtime.sendMessage({ type: "status" }, (resp) => {
      if (chrome.runtime.lastError) { render(null); return; }
      render(resp);
    });
  } catch (e) { render(null); }
}

document.getElementById("reconnect").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "reconnect" }, () => setTimeout(refresh, 800));
});
document.getElementById("opt").addEventListener("click", () => chrome.runtime.openOptionsPage());

refresh();
setInterval(refresh, 1500);
