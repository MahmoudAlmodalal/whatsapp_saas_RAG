/**
 * Rasan Chat Widget — رسن
 * Embed: <script async src="https://cdn.rasan.ai/widget.js"></script>
 * Config: window.RasanConfig = { botId, primaryColor, lang, position }
 */
(function () {
  "use strict";

  var cfg = window.RasanConfig || {};
  var BOT_ID       = cfg.botId       || "";
  var PRIMARY      = cfg.primaryColor || "#10b981";
  var LANG         = cfg.lang         || "ar";
  var POSITION     = cfg.position     || "left"; // 'left' for RTL, 'right' for LTR
  var API_BASE     = cfg.apiBase      || "";

  if (!BOT_ID) {
    console.warn("[Rasan] window.RasanConfig.botId is required.");
    return;
  }

  var IS_RTL   = LANG === "ar";
  var SESSION_KEY   = "rasan_conv_" + BOT_ID;
  var CUSTOMER_KEY  = "rasan_cid_" + BOT_ID;
  var conversationId = sessionStorage.getItem(SESSION_KEY) || null;

  function getCustomerId() {
    var id = localStorage.getItem(CUSTOMER_KEY);
    if (!id) {
      id = "web_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(CUSTOMER_KEY, id);
    }
    return id;
  }

  var customerId = getCustomerId();

  // ── Styles ──────────────────────────────────────────────────────────────────
  var style = document.createElement("style");
  style.textContent = [
    "#rasan-btn{position:fixed;bottom:20px;" + (IS_RTL ? "left" : "right") + ":20px;z-index:9999;",
    "width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg," + PRIMARY + ",#0d9488);",
    "border:none;cursor:pointer;box-shadow:0 4px 20px rgba(16,185,129,0.4);",
    "display:flex;align-items:center;justify-content:center;transition:transform .2s,box-shadow .2s;}",
    "#rasan-btn:hover{transform:scale(1.1);box-shadow:0 6px 28px rgba(16,185,129,0.5);}",
    "#rasan-btn svg{width:26px;height:26px;fill:none;stroke:#fff;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;}",
    "#rasan-pulse{position:absolute;top:0;" + (IS_RTL ? "left" : "right") + ":0;width:14px;height:14px;",
    "background:#f59e0b;border-radius:50%;border:2px solid #0f172a;animation:rasan-pulse 2s infinite;}",
    "@keyframes rasan-pulse{0%,100%{transform:scale(1);opacity:1;}50%{transform:scale(1.3);opacity:0.7;}}",
    "#rasan-panel{position:fixed;bottom:88px;" + (IS_RTL ? "left" : "right") + ":20px;z-index:9998;",
    "width:340px;height:480px;background:#0f172a;border:1px solid #1e293b;border-radius:20px;",
    "display:flex;flex-direction:column;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.6);",
    "transition:opacity .25s,transform .25s;opacity:0;transform:translateY(12px) scale(.97);pointer-events:none;}",
    "#rasan-panel.open{opacity:1;transform:translateY(0) scale(1);pointer-events:all;}",
    "#rasan-header{background:linear-gradient(135deg," + PRIMARY + ",#0d9488);padding:14px 16px;",
    "display:flex;align-items:center;justify-content:space-between;gap:10px;}",
    "#rasan-header-title{color:#fff;font-weight:800;font-size:14px;direction:" + (IS_RTL ? "rtl" : "ltr") + ";}",
    "#rasan-header-sub{color:rgba(255,255,255,.75);font-size:11px;margin-top:1px;direction:" + (IS_RTL ? "rtl" : "ltr") + ";}",
    "#rasan-close{background:rgba(255,255,255,.2);border:none;border-radius:50%;width:28px;height:28px;",
    "cursor:pointer;color:#fff;font-size:16px;display:flex;align-items:center;justify-content:center;",
    "flex-shrink:0;transition:background .2s;}",
    "#rasan-close:hover{background:rgba(255,255,255,.35);}",
    "#rasan-messages{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;}",
    "#rasan-messages::-webkit-scrollbar{width:4px;}",
    "#rasan-messages::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:4px;}",
    ".rasan-msg{max-width:82%;padding:10px 13px;border-radius:14px;font-size:13px;line-height:1.5;word-break:break-word;}",
    ".rasan-msg.customer{background:#1d4ed8;color:#fff;align-self:" + (IS_RTL ? "flex-start" : "flex-end") + ";",
    "border-bottom-" + (IS_RTL ? "left" : "right") + "-radius:3px;}",
    ".rasan-msg.ai{background:#1e293b;color:#cbd5e1;border:1px solid #334155;align-self:" + (IS_RTL ? "flex-end" : "flex-start") + ";",
    "border-bottom-" + (IS_RTL ? "right" : "left") + "-radius:3px;}",
    ".rasan-typing{display:flex;gap:5px;padding:10px 13px;background:#1e293b;border:1px solid #334155;",
    "border-radius:14px;align-self:" + (IS_RTL ? "flex-end" : "flex-start") + ";border-bottom-" + (IS_RTL ? "right" : "left") + "-radius:3px;}",
    ".rasan-typing span{width:7px;height:7px;background:#64748b;border-radius:50%;animation:rasan-bounce .9s infinite;}",
    ".rasan-typing span:nth-child(2){animation-delay:.15s;}.rasan-typing span:nth-child(3){animation-delay:.3s;}",
    "@keyframes rasan-bounce{0%,60%,100%{transform:translateY(0);}30%{transform:translateY(-6px);}}",
    "#rasan-footer{padding:10px 12px;border-top:1px solid #1e293b;display:flex;gap:8px;align-items:center;}",
    "#rasan-input{flex:1;background:#1e293b;border:1px solid #334155;border-radius:12px;",
    "padding:9px 13px;color:#f1f5f9;font-size:13px;outline:none;direction:" + (IS_RTL ? "rtl" : "ltr") + ";",
    "font-family:inherit;transition:border .2s;}",
    "#rasan-input:focus{border-color:" + PRIMARY + ";}",
    "#rasan-input::placeholder{color:#475569;}",
    "#rasan-send{background:" + PRIMARY + ";border:none;border-radius:10px;width:38px;height:38px;",
    "cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;",
    "transition:opacity .2s;} #rasan-send:hover{opacity:.85;}",
    "#rasan-send svg{width:17px;height:17px;fill:none;stroke:#fff;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;}",
    "#rasan-send:disabled{opacity:.4;cursor:default;}",
    "#rasan-branding{text-align:center;font-size:10px;color:#334155;padding:0 0 8px;}"
  ].join("");
  document.head.appendChild(style);

  // ── Markup ───────────────────────────────────────────────────────────────────
  var btn = document.createElement("button");
  btn.id = "rasan-btn";
  btn.setAttribute("aria-label", IS_RTL ? "فتح الدردشة" : "Open chat");
  btn.innerHTML = [
    '<svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    '<span id="rasan-pulse"></span>'
  ].join("");
  document.body.appendChild(btn);

  var panel = document.createElement("div");
  panel.id = "rasan-panel";
  panel.setAttribute("dir", IS_RTL ? "rtl" : "ltr");
  panel.innerHTML = [
    '<div id="rasan-header">',
    '  <div>',
    '    <div id="rasan-header-title">مساعد رسن الذكي</div>',
    '    <div id="rasan-header-sub">• متصل الآن — يرد في ثوانٍ</div>',
    '  </div>',
    '  <button id="rasan-close" aria-label="close">✕</button>',
    '</div>',
    '<div id="rasan-messages"></div>',
    '<div id="rasan-footer">',
    '  <input id="rasan-input" type="text" placeholder="' + (IS_RTL ? "اكتب رسالتك..." : "Type a message...") + '" autocomplete="off"/>',
    '  <button id="rasan-send" disabled>',
    '    <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
    '  </button>',
    '</div>',
    '<div id="rasan-branding">Powered by رسن</div>'
  ].join("");
  document.body.appendChild(panel);

  var messagesEl = document.getElementById("rasan-messages");
  var inputEl    = document.getElementById("rasan-input");
  var sendEl     = document.getElementById("rasan-send");
  var isOpen     = false;
  var isSending  = false;

  // Fetch bot name
  fetch(API_BASE + "/api/v1/tenants/" + BOT_ID)
    .then(function(r){ return r.ok ? r.json() : null; })
    .then(function(d){
      if (d && d.config && d.config.ai_persona_name) {
        document.getElementById("rasan-header-title").textContent = d.config.ai_persona_name;
      }
    })
    .catch(function(){});

  function togglePanel() {
    isOpen = !isOpen;
    panel.classList.toggle("open", isOpen);
    var pulse = document.getElementById("rasan-pulse");
    if (pulse) pulse.style.display = isOpen ? "none" : "block";
    if (isOpen && messagesEl.children.length === 0) {
      addMessage("ai", IS_RTL ? "مرحباً! كيف يمكنني مساعدتك اليوم؟" : "Hello! How can I help you today?");
      inputEl.focus();
    }
    if (isOpen) scrollToBottom();
  }

  function addMessage(role, text) {
    var div = document.createElement("div");
    div.className = "rasan-msg " + role;
    div.textContent = text;
    messagesEl.appendChild(div);
    scrollToBottom();
    return div;
  }

  function showTyping() {
    var div = document.createElement("div");
    div.className = "rasan-typing";
    div.id = "rasan-typing";
    div.innerHTML = "<span></span><span></span><span></span>";
    messagesEl.appendChild(div);
    scrollToBottom();
  }

  function hideTyping() {
    var el = document.getElementById("rasan-typing");
    if (el) el.remove();
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function sendMessage() {
    var text = inputEl.value.trim();
    if (!text || isSending) return;
    isSending = true;
    sendEl.disabled = true;
    inputEl.value = "";
    addMessage("customer", text);
    showTyping();

    var body = { message: text, customer_identifier: customerId };
    if (conversationId) body.conversation_id = conversationId;

    fetch(API_BASE + "/api/v1/chat/" + BOT_ID, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function(data) {
        hideTyping();
        if (data.conversation_id) {
          conversationId = data.conversation_id;
          sessionStorage.setItem(SESSION_KEY, conversationId);
        }
        addMessage("ai", data.reply || (IS_RTL ? "عذراً، لم أفهم سؤالك." : "Sorry, I didn't understand."));
      })
      .catch(function() {
        hideTyping();
        addMessage("ai", IS_RTL ? "عذراً، حدث خطأ. يرجى المحاولة لاحقاً." : "Sorry, an error occurred. Please try again.");
      })
      .finally(function() {
        isSending = false;
        sendEl.disabled = inputEl.value.trim() === "";
        inputEl.focus();
      });
  }

  // ── Events ───────────────────────────────────────────────────────────────────
  btn.addEventListener("click", togglePanel);
  document.getElementById("rasan-close").addEventListener("click", togglePanel);

  inputEl.addEventListener("input", function() {
    sendEl.disabled = inputEl.value.trim() === "" || isSending;
  });

  inputEl.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendEl.addEventListener("click", sendMessage);

  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && isOpen) togglePanel();
  });

})();
