async function load() {
  const c = await chrome.storage.local.get(["token", "daemonUrl"]);
  document.getElementById("token").value = c.token || "";
  if (c.daemonUrl) document.getElementById("url").value = c.daemonUrl;
}

document.getElementById("save").addEventListener("click", async () => {
  await chrome.storage.local.set({
    token: document.getElementById("token").value.trim(),
    daemonUrl: document.getElementById("url").value.trim(),
  });
  document.getElementById("msg").textContent = "Salvato. L'estensione si ricollega entro pochi secondi.";
});

load();
