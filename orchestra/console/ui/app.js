(() => {
  "use strict";

  const REFRESH_MS = 15000;
  const MSG_MS = 5000;

  const state = {
    status: null,
    radar: null,
    messages: null,
    events: [],
    tab: "today",
  };

  const $ = (id) => document.getElementById(id);

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function onlineClass(text) {
    const t = String(text || "");
    if (t.includes("在线") && !t.includes("离线")) return "status-online";
    if (t.includes("离线") || t.includes("未配置")) return "status-offline";
    return "status-degraded";
  }

  function badgeClass(status) {
    const s = String(status || "").toLowerCase();
    if (s.includes("done") || s.includes("ok") || s.includes("success")) return "done";
    if (s.includes("fail") || s.includes("error")) return "failed";
    if (s.includes("run") || s.includes("active") || s.includes("pending")) return "running";
    return "";
  }

  async function fetchJson(path) {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(`${path} ${res.status}`);
    return res.json();
  }

  async function fetchText(path) {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(`${path} ${res.status}`);
    return res.text();
  }

  function parseIcs(text, layer) {
    const events = [];
    const blocks = text.split("BEGIN:VEVENT").slice(1);
    for (const block of blocks) {
      const body = block.split("END:VEVENT")[0] || "";
      const summary = matchProp(body, "SUMMARY") || "(无标题)";
      const dt = matchProp(body, "DTSTART");
      const desc = matchProp(body, "DESCRIPTION") || "";
      const start = parseIcsDate(dt);
      if (!start) continue;
      events.push({
        layer,
        title: unescapeIcs(summary),
        note: unescapeIcs(desc),
        start,
      });
    }
    return events;
  }

  function matchProp(body, name) {
    const re = new RegExp(`^${name}(?:;[^:\\n]*)?:(.*)$`, "mi");
    const m = body.match(re);
    if (!m) return null;
    let val = m[1].trim();
    // unfold continued lines
    const lines = body.split(/\r?\n/);
    let hit = false;
    for (const line of lines) {
      if (!hit) {
        if (re.test(line)) hit = true;
        continue;
      }
      if (/^[ \t]/.test(line)) val += line.slice(1);
      else break;
    }
    return val;
  }

  function unescapeIcs(s) {
    return String(s)
      .replace(/\\n/gi, "\n")
      .replace(/\\,/g, ",")
      .replace(/\\;/g, ";")
      .replace(/\\\\/g, "\\");
  }

  function parseIcsDate(raw) {
    if (!raw) return null;
    // floating local or Z
    const m = String(raw).match(
      /^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2}))?(Z)?$/,
    );
    if (!m) return null;
    const [, Y, Mo, D, h = "00", mi = "00", s = "00", z] = m;
    if (z) {
      return new Date(Date.UTC(+Y, +Mo - 1, +D, +h, +mi, +s));
    }
    return new Date(+Y, +Mo - 1, +D, +h, +mi, +s);
  }

  function dayKey(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function formatDayLabel(d, todayKey) {
    const key = dayKey(d);
    const wd = ["日", "一", "二", "三", "四", "五", "六"][d.getDay()];
    const label = `${d.getMonth() + 1}月${d.getDate()}日 · 周${wd}`;
    return { key, label, isToday: key === todayKey };
  }

  function formatHM(d) {
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function formatStamp(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return `${dayKey(d)} ${formatHM(d)}`;
  }

  function renderPulse(targetId, status) {
    const el = $(targetId);
    if (!el || !status) {
      if (el) el.innerHTML = `<div class="empty">无状态数据</div>`;
      return;
    }
    const cards = [
      { label: "4B", value: status["4b"] || "—", sub: "broker" },
      { label: "核桃派", value: status.walnut || "—", sub: "monitor" },
      { label: "Windows", value: status.windows || "—", sub: "本机" },
      {
        label: "队列",
        value: status.queue_len == null ? "—" : String(status.queue_len),
        sub: `活动 ${status.active_tasks == null ? "—" : status.active_tasks}`,
        mono: true,
      },
      {
        label: "下一触发",
        value: (status.next && status.next[0] && status.next[0].label) || "—",
        sub: (status.next && status.next[0] && status.next[0].in_text) || "",
      },
      {
        label: "生成",
        value: status.generated_text || "—",
        sub: status.degraded ? "降级" : "正常",
        mono: true,
      },
    ];
    el.innerHTML = cards
      .map((c) => {
        const cls = ["4B", "核桃派", "Windows"].includes(c.label)
          ? onlineClass(c.value)
          : "";
        return `<div class="pulse-card">
          <div class="pulse-label">${esc(c.label)}</div>
          <div class="pulse-value ${c.mono ? "mono" : ""} ${cls}">${esc(c.value)}</div>
          <div class="pulse-sub">${esc(c.sub)}</div>
        </div>`;
      })
      .join("");
  }

  function renderAgenda(events) {
    const el = $("agenda");
    if (!el) return;
    const now = new Date();
    const today = dayKey(now);
    const start = new Date(now);
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - 3);
    const end = new Date(now);
    end.setHours(23, 59, 59, 999);
    end.setDate(end.getDate() + 7);

    const filtered = events
      .filter((e) => e.start >= start && e.start <= end)
      .sort((a, b) => a.start - b.start)
      .slice(0, 40);

    if (!filtered.length) {
      el.innerHTML = `<div class="empty">窗口内无日程（昨3天 → 未7天）</div>`;
      return;
    }

    const groups = new Map();
    for (const ev of filtered) {
      const meta = formatDayLabel(ev.start, today);
      if (!groups.has(meta.key)) groups.set(meta.key, { meta, items: [] });
      groups.get(meta.key).items.push(ev);
    }

    el.innerHTML = [...groups.values()]
      .map(({ meta, items }) => {
        const rows = items
          .map(
            (ev) => `<div class="event">
            <div class="event-time">${esc(formatHM(ev.start))}</div>
            <div class="event-rail ${esc(ev.layer)}"></div>
            <div>
              <div class="event-title">${esc(ev.title)}</div>
              ${ev.note ? `<div class="event-note">${esc(ev.note)}</div>` : ""}
            </div>
            <div class="event-layer">${esc(ev.layer === "system" ? "系统" : "个人")}</div>
          </div>`,
          )
          .join("");
        return `<div class="day-group">
          <div class="day-label ${meta.isToday ? "is-today" : ""}">${esc(meta.label)}${meta.isToday ? " · 今天" : ""}</div>
          ${rows}
        </div>`;
      })
      .join("");
  }

  function renderNext(targetId, next) {
    const el = $(targetId);
    if (!el) return;
    const list = Array.isArray(next) ? next : [];
    if (!list.length) {
      el.innerHTML = `<div class="empty">无下次触发</div>`;
      return;
    }
    el.innerHTML = list
      .slice(0, 6)
      .map(
        (n) => `<div class="next-item">
        <div>
          <span class="next-label">${esc(n.label || "—")}</span>
          <span class="next-at">${esc(n.at || "")}</span>
        </div>
        <div class="next-eta">${esc(n.in_text || "—")}</div>
      </div>`,
      )
      .join("");
  }

  function renderMessages(list, targetId, tone) {
    const el = $(targetId);
    if (!el) return;
    const items = Array.isArray(list) ? list : [];
    if (!items.length) {
      el.innerHTML = `<div class="empty">暂无</div>`;
      return;
    }
    el.innerHTML = items
      .slice(0, 6)
      .map(
        (m) => `<article class="msg ${tone || ""}">
        <div class="msg-title">${esc(m.title || "留言")}</div>
        <div class="msg-meta">${esc(m.time_text || m.time || "")}</div>
        ${m.text ? `<div class="msg-text">${esc(m.text)}</div>` : ""}
      </article>`,
      )
      .join("");
  }

  function renderRadar(radar) {
    const meta = $("radar-meta");
    const stages = $("radar-stages");
    const top5 = $("radar-top5");
    const digest = $("radar-digest");
    if (!radar || !radar.available) {
      if (meta) meta.innerHTML = `<div class="meta-pill">雷达数据不可用</div>`;
      if (stages) stages.innerHTML = `<div class="empty">无阶段数据</div>`;
      if (top5) top5.innerHTML = `<div class="empty">无 Top5</div>`;
      if (digest) digest.textContent = "无日报";
      return;
    }

    meta.innerHTML = [
      ["日期", radar.date || "—"],
      ["模式", radar.mode || "—"],
      ["校验", radar.validation == null ? "—" : String(radar.validation)],
    ]
      .map(
        ([k, v]) =>
          `<div class="meta-pill">${esc(k)} <strong>${esc(v)}</strong></div>`,
      )
      .join("");

    const st = Array.isArray(radar.stages) ? radar.stages : [];
    stages.innerHTML = st.length
      ? st
          .map((s) => {
            const status = String(s.status || "unknown").toLowerCase();
            return `<div class="stage">
              <div class="stage-dot ${esc(status)}"></div>
              <div class="stage-name">${esc(s.name || "—")}</div>
              <div class="stage-status">${esc(s.status || "—")}</div>
              <div class="stage-time">${esc(s.time ? formatStamp(s.time) : "—")}</div>
            </div>`;
          })
          .join("")
      : `<div class="empty">无阶段</div>`;

    const tops = Array.isArray(radar.top5) ? radar.top5 : [];
    const maxScore = Math.max(100, ...tops.map((t) => Number(t.total) || 0));
    top5.innerHTML = tops.length
      ? tops
          .map((t, i) => {
            const score = Number(t.total) || 0;
            const pct = Math.max(4, Math.round((score / maxScore) * 100));
            return `<div class="top-item">
              <div class="top-rank">${String(i + 1).padStart(2, "0")}</div>
              <div>
                <div class="top-title">${esc(t.title || "—")}</div>
                <div class="top-id">${esc(t.id || "")}</div>
              </div>
              <div class="top-score">${esc(score)}</div>
              <div class="top-bar"><span style="width:${pct}%"></span></div>
            </div>`;
          })
          .join("")
      : `<div class="empty">无 Top5</div>`;

    digest.textContent = radar.digest_txt || "无日报正文";
  }

  function renderRows(targetId, items, mapFn) {
    const el = $(targetId);
    if (!el) return;
    const list = Array.isArray(items) ? items : [];
    if (!list.length) {
      el.innerHTML = `<div class="empty">无数据</div>`;
      return;
    }
    el.innerHTML = list.map(mapFn).join("");
  }

  function renderTasks(status) {
    const recent = (status && status.recent_tasks) || [];
    const attempts = (status && status.attempts) || [];
    const experiments =
      (status && status.experiments && status.experiments.cards) || [];
    const expAvailable =
      status && status.experiments && status.experiments.available;

    renderRows("recent-tasks", recent, (t) => {
      const name = t.slug || t.id || t.task || "—";
      const st = t.status || "—";
      return `<div class="row">
        <div class="row-main">${esc(name)}</div>
        <span class="badge ${badgeClass(st)}">${esc(st)}</span>
      </div>`;
    });

    renderRows("attempts", attempts, (a) => {
      const st = a.status || "—";
      return `<div class="row">
        <div class="row-main">${esc(a.task || "—")}</div>
        <span class="badge ${badgeClass(st)}">${esc(st)}</span>
        <div class="row-sub">attempt ${esc(a.attempt ?? "—")} · ${esc(formatStamp(a.started_at))}</div>
      </div>`;
    });

    const expEl = $("experiments");
    if (!expAvailable) {
      expEl.innerHTML = `<div class="empty">实验卡目录未初始化</div>`;
    } else {
      renderRows("experiments", experiments, (c) => {
        const st = c.status || "—";
        return `<div class="row">
          <div class="row-main">${esc(c.id || "—")}</div>
          <span class="badge ${badgeClass(st)}">${esc(st)}</span>
        </div>`;
      });
    }
  }

  function renderSystem(status) {
    const devices = $("devices");
    if (!status) {
      devices.innerHTML = `<div class="empty">无状态</div>`;
      return;
    }
    const cards = [
      { name: "4B", state: status["4b"], detail: "orchestra reporter" },
      { name: "核桃派", state: status.walnut, detail: "usage-monitor" },
      { name: "Windows", state: status.windows, detail: `同步 ${status.last_sync_text || "—"}` },
    ];
    devices.innerHTML = cards
      .map(
        (c) => `<div class="device">
        <div class="device-name">${esc(c.name)}</div>
        <div class="device-state ${onlineClass(c.state)}">${esc(c.state || "—")}</div>
        <div class="device-detail">${esc(c.detail)}</div>
      </div>`,
      )
      .join("");

    renderNext("system-next", status.next || []);

    const meta = $("system-meta");
    const rows = [
      ["数据生成", status.generated_text || "—"],
      ["最近任务", status.last_task || "—"],
      ["上次同步", status.last_sync_text || "—"],
      ["降级", status.degraded ? "是" : "否"],
      ["降级说明", status.degraded_reason || "—"],
      ["队列", status.queue_len == null ? "—" : String(status.queue_len)],
      ["活动", status.active_tasks == null ? "—" : String(status.active_tasks)],
    ];
    meta.innerHTML = rows
      .map(
        ([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`,
      )
      .join("");
  }

  function renderBanner(status) {
    const el = $("banner");
    if (!status || !status.degraded) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.classList.remove("hidden");
    const reason = status.degraded_reason || "degraded";
    el.textContent = `降级运行：${reason}（设备区可能离线/缺 token，其余模块继续展示本地缓存）`;
  }

  function renderAll() {
    const { status, radar, messages, events } = state;
    renderBanner(status);
    renderPulse("pulse", status);
    renderPulse("tasks-pulse", status);
    renderAgenda(events);
    renderNext("next-list", (status && status.next) || []);
    renderMessages((messages && messages.latest) || [], "messages-latest", "");
    renderMessages((messages && messages.pending) || [], "messages-pending", "pending");
    renderMessages((messages && messages.alerts) || [], "messages-alerts", "alert");
    $("msg-count").textContent = String(((messages && messages.latest) || []).length);
    $("pending-count").textContent = String(((messages && messages.pending) || []).length);
    $("alert-count").textContent = String(((messages && messages.alerts) || []).length);
    renderRadar(radar);
    renderTasks(status);
    renderSystem(status);
    $("foot-gen").textContent = status && status.generated_text
      ? `生成 ${status.generated_text}`
      : "—";
  }

  async function loadCore() {
    const [status, radar, messages, systemIcs, personalIcs] = await Promise.all([
      fetchJson("/status.json"),
      fetchJson("/radar.json"),
      fetchJson("/messages.json"),
      fetchText("/system.ics"),
      fetchText("/personal.ics"),
    ]);
    state.status = status;
    state.radar = radar;
    state.messages = messages;
    state.events = [
      ...parseIcs(systemIcs, "system"),
      ...parseIcs(personalIcs, "personal"),
    ];
    renderAll();
  }

  async function loadMessagesOnly() {
    state.messages = await fetchJson("/messages.json");
    renderMessages((state.messages && state.messages.latest) || [], "messages-latest", "");
    renderMessages((state.messages && state.messages.pending) || [], "messages-pending", "pending");
    renderMessages((state.messages && state.messages.alerts) || [], "messages-alerts", "alert");
    $("msg-count").textContent = String(((state.messages && state.messages.latest) || []).length);
    $("pending-count").textContent = String(((state.messages && state.messages.pending) || []).length);
    $("alert-count").textContent = String(((state.messages && state.messages.alerts) || []).length);
  }

  function setTab(name) {
    state.tab = name;
    document.querySelectorAll(".tab").forEach((btn) => {
      const on = btn.dataset.tab === name;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    ["today", "radar", "tasks", "system"].forEach((id) => {
      const page = $(`page-${id}`);
      const on = id === name;
      page.classList.toggle("is-active", on);
      page.hidden = !on;
    });
    history.replaceState(null, "", `#${name}`);
  }

  function tickClock() {
    const now = new Date();
    $("clock").textContent = `${dayKey(now)} ${formatHM(now)}:${String(now.getSeconds()).padStart(2, "0")}`;
  }

  function bind() {
    document.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => setTab(btn.dataset.tab));
    });
    $("btn-refresh").addEventListener("click", () => {
      loadCore().catch((err) => {
        $("banner").classList.remove("hidden");
        $("banner").textContent = `刷新失败：${err.message}`;
      });
    });
    window.addEventListener("hashchange", () => {
      const h = (location.hash || "").replace(/^#/, "");
      if (["today", "radar", "tasks", "system"].includes(h)) setTab(h);
    });
    const hash = (location.hash || "").replace(/^#/, "");
    if (["today", "radar", "tasks", "system"].includes(hash)) setTab(hash);
  }

  bind();
  tickClock();
  setInterval(tickClock, 1000);
  loadCore().catch((err) => {
    $("banner").classList.remove("hidden");
    $("banner").textContent = `加载失败：${err.message}`;
  });
  setInterval(() => {
    loadCore().catch(() => {});
  }, REFRESH_MS);
  setInterval(() => {
    loadMessagesOnly().catch(() => {});
  }, MSG_MS);
})();
