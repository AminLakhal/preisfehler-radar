(() => {
  const $ = (id) => document.getElementById(id);
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  };

  let deals = [];
  let filter = store.get("filter", "amazon");
  let seen = new Set();
  let firstLoad = true;

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function ago(iso) {
    const s = Math.max(0, (Date.now() - new Date(iso)) / 1000);
    if (s < 90) return "gerade eben";
    if (s < 3600) return `vor ${Math.round(s / 60)} Min.`;
    if (s < 86400) return `vor ${Math.round(s / 3600)} Std.`;
    return `vor ${Math.round(s / 86400)} Tg.`;
  }

  function render() {
    const q = $("q").value.trim().toLowerCase();
    const list = deals.filter((d) => (filter === "all" || d.amazon) && (!q || (d.title + " " + d.merchant).toLowerCase().includes(q)));
    $("list").innerHTML = list.map((d) => {
      const fresh = Date.now() - new Date(d.published) < 3600e3;
      const thumb = d.image ? `style="background-image:url('${esc(d.image)}')"` : "";
      return `<a class="card${fresh ? " fresh" : ""}" href="${esc(d.url)}" target="_blank" rel="noopener noreferrer">
        <div class="thumb" ${thumb}>${d.image ? "" : "🏷️"}</div>
        <div class="body">
          <h3>${esc(d.title)}</h3>
          <div class="meta">
            ${d.price_text ? `<span class="price">${esc(d.price_text)}</span>` : ""}
            <span class="tag${d.amazon ? " amz" : ""}">${esc(d.merchant || "Shop")}</span>
            <span>${ago(d.published)}</span>
          </div>
        </div></a>`;
    }).join("");
    $("empty").hidden = list.length > 0;
  }

  function stats(updated) {
    const day = new Date(); day.setHours(0, 0, 0, 0);
    $("st-total").textContent = deals.length;
    $("st-amazon").textContent = deals.filter((d) => d.amazon).length;
    $("st-today").textContent = deals.filter((d) => new Date(d.published) >= day).length;
    $("st-updated").textContent = updated ? ago(updated) : "–";
  }

  function browserNotify(fresh) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    fresh.filter((d) => d.amazon).forEach((d) => {
      const n = new Notification(`Preisfehler: ${d.merchant || "Amazon"} ${d.price_text || ""}`.trim(), { body: d.title, tag: d.id });
      n.onclick = () => window.open(d.url, "_blank");
    });
  }

  async function load() {
    try {
      const r = await fetch("deals.json?t=" + Date.now(), { cache: "no-store" });
      const data = await r.json();
      deals = data.deals || [];
      const fresh = deals.filter((d) => !seen.has(d.id));
      if (!firstLoad) browserNotify(fresh);
      deals.forEach((d) => seen.add(d.id));
      firstLoad = false;
      stats(data.updated);
      render();
    } catch (e) {
      $("list").innerHTML = "";
      $("empty").hidden = false;
      $("empty").textContent = "Daten konnten nicht geladen werden.";
    }
  }

  // Filter
  document.querySelectorAll("#seg button").forEach((b) => {
    b.classList.toggle("on", b.dataset.f === filter);
    b.onclick = () => {
      filter = b.dataset.f; store.set("filter", filter);
      document.querySelectorAll("#seg button").forEach((x) => x.classList.toggle("on", x === b));
      render();
    };
  });
  $("q").addEventListener("input", render);

  // Browser-Benachrichtigung (nur solange der Tab offen ist)
  $("bell").onclick = async () => {
    if (!("Notification" in window)) return alert("Dein Browser unterstützt keine Benachrichtigungen.");
    const p = await Notification.requestPermission();
    $("bell").textContent = p === "granted" ? "🔔 Browser-Alarm aktiv" : "🔕 Nicht erlaubt";
  };
  if ("Notification" in window && Notification.permission === "granted") $("bell").textContent = "🔔 Browser-Alarm aktiv";

  // ntfy-Thema
  const topic = $("topic");
  const sub = $("sub");
  function syncTopic() {
    const t = topic.value.trim().replace(/[^A-Za-z0-9_-]/g, "");
    store.set("topic", t);
    sub.setAttribute("aria-disabled", t.length < 8 ? "true" : "false");
    sub.href = t.length < 8 ? "#alarm" : `ntfy://ntfy.sh/${t}`;
    $("topic-note").textContent = t.length && t.length < 8
      ? "Zu kurz – nimm mindestens 8 Zeichen, sonst kann jeder mitlesen."
      : "Wird nur in deinem Browser gespeichert.";
  }
  topic.value = store.get("topic", "");
  topic.addEventListener("input", syncTopic);
  syncTopic();

  load();
  setInterval(load, 60000);
})();
