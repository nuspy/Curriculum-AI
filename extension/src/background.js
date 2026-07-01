// AutoJob Bridge — service worker (MV3).
// WS verso il daemon (/ext) con token; esegue i comandi via chrome.scripting/chrome.debugger;
// imposta il badge duplicate-guard; intercetta gli "Apply" che aprono nuovi tab.
import { buildSnapshot } from "./snapshot.js";
import { actOnIndex, detectCaptchaInPage, extractIdentity, getPageText } from "./page_actions.js";

const DEFAULT_URL = "ws://127.0.0.1:8765/ext";
let ws = null;
let connected = false;
let activeTabId = null;
let backoff = 1000;
const queryTab = new Map(); // queryId -> tabId (per il badge)

async function cfg() {
  const c = await chrome.storage.local.get(["token", "daemonUrl"]);
  return { token: c.token || "", url: c.daemonUrl || DEFAULT_URL };
}

function send(obj) {
  try { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); } catch (e) {}
}

async function getActiveTab() {
  if (activeTabId != null) {
    try { const t = await chrome.tabs.get(activeTabId); if (t) return t; } catch (e) {}
  }
  const [t] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (t) activeTabId = t.id;
  return t;
}

async function runInPage(tabId, func, args = [], world = "ISOLATED") {
  const [res] = await chrome.scripting.executeScript({ target: { tabId }, func, args, world });
  return res ? res.result : null;
}

async function uploadViaDebugger(tabId, index, paths) {
  const target = { tabId };
  try {
    await chrome.debugger.attach(target, "1.3");
    const { root } = await chrome.debugger.sendCommand(target, "DOM.getDocument", { depth: -1 });
    const { nodeId } = await chrome.debugger.sendCommand(target, "DOM.querySelector", {
      nodeId: root.nodeId, selector: '[data-aj-index="' + index + '"]',
    });
    if (!nodeId) return { ok: false, index, error_kind: "not_found" };
    await chrome.debugger.sendCommand(target, "DOM.setFileInputFiles", { nodeId, files: paths });
    return { ok: true, index, value_after: paths.join(";") };
  } catch (e) {
    return { ok: false, index, error_kind: "not_interactable", message: String(e).slice(0, 200) };
  } finally {
    try { await chrome.debugger.detach(target); } catch (e) {}
  }
}

async function handleCommand(msg) {
  const id = msg.id;
  const p = msg.payload || {};
  let payload = {};
  try {
    const tab = await getActiveTab();
    const tabId = tab && tab.id;
    switch (msg.type) {
      case "cmd.get_snapshot":
        payload = await runInPage(tabId, buildSnapshot);
        break;
      case "cmd.page_text":
        payload = { text: await runInPage(tabId, getPageText) };
        break;
      case "cmd.detect_captcha":
        payload = await runInPage(tabId, detectCaptchaInPage);
        break;
      case "cmd.current_url":
        payload = { url: tab ? tab.url : "" };
        break;
      case "cmd.current_target":
        payload = { target_id: String(tabId) };
        break;
      case "cmd.navigate":
        await chrome.tabs.update(tabId, { url: p.url });
        payload = { ok: true, message: "navigated" };
        break;
      case "cmd.open_tab": {
        const nt = await chrome.tabs.create({ url: p.url, active: true });
        activeTabId = nt.id;
        await new Promise((res) => {
          const lsn = (id, info) => { if (id === nt.id && info.status === "complete") { try { chrome.tabs.onUpdated.removeListener(lsn); } catch (e) {} res(); } };
          chrome.tabs.onUpdated.addListener(lsn);
          setTimeout(() => { try { chrome.tabs.onUpdated.removeListener(lsn); } catch (e) {} res(); }, 15000);
        });
        let cur = nt; try { cur = await chrome.tabs.get(nt.id); } catch (e) {}
        payload = { target_id: String(nt.id), url: cur ? cur.url : p.url };
        break;
      }
      case "cmd.list_targets": {
        const tabs = await chrome.tabs.query({});
        payload = { targets: tabs.map((t) => ({ target_id: String(t.id), type: "tab", url: t.url, title: t.title, active: t.id === tabId })) };
        break;
      }
      case "cmd.switch_target":
        activeTabId = parseInt(p.target_id, 10);
        try { await chrome.tabs.update(activeTabId, { active: true }); } catch (e) {}
        payload = { ok: true, message: "switched" };
        break;
      case "cmd.close_target":
        try { await chrome.tabs.remove(parseInt(p.target_id, 10)); payload = { ok: true }; }
        catch (e) { payload = { ok: false, error_kind: "not_found" }; }
        break;
      case "cmd.wait_new_target": {
        const since = new Set((p.since || []).map(String));
        let found = null;
        for (let i = 0; i < (p.timeout_ms || 8000) / 150; i++) {
          const tabs = await chrome.tabs.query({});
          found = tabs.find((t) => !since.has(String(t.id)));
          if (found) break;
          await new Promise((r) => setTimeout(r, 150));
        }
        payload = { target: found ? { target_id: String(found.id), type: "tab", url: found.url, title: found.title } : null };
        break;
      }
      case "cmd.wait_dom":
        await new Promise((r) => setTimeout(r, Math.min(1500, p.timeout_ms || 1500)));
        payload = { changed: true };
        break;
      case "cmd.eval":
        payload = { result: await runInPage(tabId, (expr) => { try { return eval(expr); } catch (e) { return null; } }, [p.expr], p.world === "MAIN" ? "MAIN" : "ISOLATED") };
        break;
      case "cmd.screenshot":
        try { payload = { base64: (await chrome.tabs.captureVisibleTab()).split(",")[1] }; }
        catch (e) { payload = { base64: null }; }
        break;
      case "cmd.action": {
        if (p.op === "upload") {
          payload = await uploadViaDebugger(tabId, p.index, p.paths || []);
        } else if (p.op === "click" && p.expect_new_target) {
          const before = (await chrome.tabs.query({})).map((t) => String(t.id));
          await runInPage(tabId, actOnIndex, ["click", p.index, null], "MAIN");
          let opened = null;
          for (let i = 0; i < 20; i++) {
            const tabs = await chrome.tabs.query({});
            const nt = tabs.find((t) => !before.includes(String(t.id)));
            if (nt) { opened = { target_id: String(nt.id), type: "tab", url: nt.url, title: nt.title, opener_id: String(tabId) }; break; }
            await new Promise((r) => setTimeout(r, 150));
          }
          payload = { ok: true, index: p.index, dom_changed: true, opened_target: opened };
        } else {
          const val = p.op === "checkbox" ? p.checked : (p.op === "key" ? p.key : (p.op === "select" ? (p.value ?? p.label) : (p.op === "scroll" ? p.index : p.value)));
          payload = await runInPage(tabId, actOnIndex, [p.op, p.index, val], "MAIN");
        }
        break;
      }
      default:
        payload = { ok: false, error_kind: "unknown_cmd" };
    }
  } catch (e) {
    payload = { ok: false, error_kind: "exception", message: String(e).slice(0, 200) };
  }
  send({ v: 1, corr: id, type: "result", payload });
}

// ---- Duplicate-guard badge ----
async function checkApplied(tabId) {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab || !/^https?:/.test(tab.url || "")) return;
    const ident = await runInPage(tabId, extractIdentity);
    const qid = "q-" + Date.now() + "-" + tabId;
    queryTab.set(qid, tabId);
    send({ v: 1, id: qid, type: "query.applied", payload: { job_identity: { url: ident.url, title: ident.title } } });
  } catch (e) {}
}

function onAppliedStatus(msg) {
  const tabId = queryTab.get(msg.corr);
  queryTab.delete(msg.corr);
  if (tabId == null) return;
  const st = msg.payload || {};
  if (st.state === "submitted") {
    chrome.action.setBadgeText({ tabId, text: "!" });
    chrome.action.setBadgeBackgroundColor({ tabId, color: st.strength === "strong" ? "#d11" : "#e80" });
    chrome.action.setTitle({ tabId, title: "AutoJob: gia candidato (" + (st.strength || "") + ") — puoi inviare di nuovo" });
  } else {
    chrome.action.setBadgeText({ tabId, text: "" });
  }
}

// ---- WS lifecycle ----
let lastError = "";
let lastAutofill = null;
async function connect() {
  const { token, url } = await cfg();
  if (!token) { lastError = "token mancante"; console.log("[AutoJob] token mancante: aprire le opzioni"); return; }
  lastError = "connessione in corso…";
  try { ws = new WebSocket(url); } catch (e) { lastError = "URL non valido: " + url; scheduleReconnect(); return; }
  ws.onopen = () => { send({ v: 1, id: "auth", type: "auth", payload: { token, ext_version: "0.1.0", browser: "opera" } }); };
  ws.onmessage = (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (msg.type === "auth_ok") { connected = true; lastError = ""; backoff = 1000; console.log("[AutoJob] connesso al daemon"); }
    else if (msg.type === "auth_err") { connected = false; lastError = "token errato"; console.warn("[AutoJob] auth fallita:", msg.payload); }
    else if (msg.type === "applied_status") onAppliedStatus(msg);
    else if (msg.type === "autofill_result") { lastAutofill = msg.payload; console.log("[AutoJob] autofill:", msg.payload); }
    else if (typeof msg.type === "string" && msg.type.startsWith("cmd.")) handleCommand(msg);
  };
  ws.onclose = () => { connected = false; if (!lastError || lastError === "connessione in corso…") lastError = "daemon non raggiungibile su " + url; scheduleReconnect(); };
  ws.onerror = () => { connected = false; lastError = "errore WebSocket (daemon spento o URL errato)"; try { ws.close(); } catch (e) {} };
}

function scheduleReconnect() {
  backoff = Math.min(backoff * 2, 30000);
  setTimeout(connect, backoff);
}

// Stato per il popup (auto-diagnosi)
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "status") {
    cfg().then((c) => sendResponse({ connected, hasToken: !!c.token, url: c.url, wsState: ws ? ws.readyState : -1, lastError, lastAutofill }));
    return true;
  }
  if (msg && msg.type === "autofill") {
    lastAutofill = { pending: true };
    send({ v: 1, id: "af-" + Date.now(), type: "autofill_request", payload: {} });
    sendResponse({ ok: connected });
    return true;
  }
  if (msg && msg.type === "reconnect") {
    try { if (ws) ws.close(); } catch (e) {}
    connect();
    sendResponse({ ok: true });
    return true;
  }
});

chrome.alarms.create("keepalive", { periodInMinutes: 0.4 });
chrome.alarms.onAlarm.addListener((a) => {
  if (a.name !== "keepalive") return;
  if (ws && ws.readyState === 1) send({ v: 1, type: "ping", payload: {} });
  else connect();
});

chrome.tabs.onActivated.addListener(({ tabId }) => { activeTabId = tabId; checkApplied(tabId); });
chrome.tabs.onUpdated.addListener((tabId, info) => { if (info.status === "complete") checkApplied(tabId); });
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
connect();
