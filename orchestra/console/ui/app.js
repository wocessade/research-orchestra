(() => {
  "use strict";

  const REFRESH_MS = 15000;
  const MSG_MS = 5000;

  const state = {
    status: null,
    radar: null,
    messages: null,
    events: [],
    personal: [],
    editingId: "",
    monthCursor: null,
    focusDay: "",
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
    if (t.includes("未配置")) return "status-degraded";
    if (t.includes("在线") && !t.includes("离线")) return "status-online";
    if (t.includes("离线")) return "status-offline";
    return "status-degraded";
  }

  function liveKind(text) {
    const c = onlineClass(text);
    if (c === "status-online") return "online";
    if (c === "status-offline") return "offline";
    return "degraded";
  }

  function badgeClass(status) {
    const s = String(status || "").toLowerCase();
    if (s.includes("queue") || s.includes("wait") || s.includes("pending")) return "queued";
    if (s.includes("fail") || s.includes("error") || s.includes("timeout") || s.includes("block") || s.includes("hung") || s.includes("stale")) return "hung";
    if (s.includes("done") || s.includes("ok") || s.includes("success") || s === "完成") return "done";
    if (s.includes("run") || s.includes("active")) return "running";
    return "";
  }

  const BUCKET_LABEL = { queued: "排队", running: "运行中", done: "完成", hung: "挂起" };
  const HUNG_AFTER_MS = 2 * 3600 * 1000;

  function taskBucket(item) {
    const raw = String(item && item.status || "").toLowerCase();
    const started = Date.parse(item && (item.started_at || item.ts) || "");
    if (raw.includes("fail") || raw.includes("error") || raw.includes("timeout") || raw.includes("block") || raw.includes("hung") || raw.includes("stale")) {
      return "hung";
    }
    if (raw.includes("run") || raw.includes("active")) {
      if (Number.isFinite(started) && Date.now() - started > HUNG_AFTER_MS) return "hung";
      return "running";
    }
    if (raw.includes("queue") || raw.includes("pending") || raw.includes("wait")) return "queued";
    return "done";
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
        uid: matchProp(body, "UID") || "",
        seriesId: matchProp(body, "X-ORCHESTRA-SERIES") || matchProp(body, "UID") || "",
        repeat: (matchProp(body, "X-ORCHESTRA-REPEAT") || "").toLowerCase(),
        done: (matchProp(body, "STATUS") || "") === "COMPLETED",
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

  function renderLivebar(status) {
    const el = $("livebar");
    if (!el) return;
    if (!status) {
      el.innerHTML = "";
      return;
    }
    const pills = [
      { name: "RK3528", state: status.broker || status["4b"] || "—" },
      { name: "核桃派", state: status.walnut || "—" },
      { name: "Windows", state: status.windows || "—" },
    ];
    el.innerHTML = pills
      .map(
        (p) => `<div class="live-pill ${liveKind(p.state)}">
        <span class="live-dot" aria-hidden="true"></span>
        <span class="live-name">${esc(p.name)}</span>
        <span class="live-state">${esc(p.state)}</span>
      </div>`,
      )
      .join("");
  }

  function upcomingFromEvents(events) {
    const now = new Date();
    const horizon = new Date(now);
    horizon.setHours(23, 59, 59, 999);
    horizon.setDate(horizon.getDate() + 14);
    const today = new Date(now);
    today.setHours(0, 0, 0, 0);
    const rows = [];
    for (const ev of events || []) {
      if (ev.layer !== "personal" || ev.done) continue;
      if (ev.start < now || ev.start > horizon) continue;
      const day = new Date(ev.start);
      day.setHours(0, 0, 0, 0);
      const daysLeft = Math.round((day - today) / 86400000);
      const urg = personalUrgency(ev.start);
      let urgency = "due-14";
      if (urg === "due-0" || urg === "due-2" || urg === "due-7") urgency = urg;
      let inText = `${daysLeft} 天后`;
      if (daysLeft === 0) inText = `今天 ${formatHM(ev.start)}`;
      else if (daysLeft === 1) inText = "明天";
      rows.push({
        title: ev.title,
        at: `${dayKey(ev.start)} ${formatHM(ev.start)}`,
        in_text: inText,
        note: ev.note || "",
        days_left: daysLeft,
        urgency,
        start: ev.start,
      });
    }
    rows.sort((a, b) => a.start - b.start || String(a.title).localeCompare(b.title));
    return rows;
  }

  function renderPulse(targetId, status) {
    const el = $(targetId);
    if (!el || !status) {
      if (el) el.innerHTML = `<div class="empty">无状态数据</div>`;
      return;
    }
    const upcoming = upcomingFromEvents(state.events);
    const soon = upcoming[0] || ((status && status.upcoming_personal) || [])[0];
    const cards = [
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
        label: "临近",
        value: soon ? soon.title : "无",
        sub: soon ? soon.in_text : "14天内无个人事项",
      },
      {
        label: "生成",
        value: status.generated_text || "—",
        sub: status.degraded ? "降级" : "正常",
        mono: true,
      },
    ];
    el.innerHTML = cards
      .map(
        (c) => `<div class="pulse-card">
          <div class="pulse-label">${esc(c.label)}</div>
          <div class="pulse-value ${c.mono ? "mono" : ""}">${esc(c.value)}</div>
          <div class="pulse-sub">${esc(c.sub)}</div>
        </div>`,
      )
      .join("");
  }

  function addDaysISO(iso, n) {
    const d = new Date(`${iso}T00:00:00`);
    d.setDate(d.getDate() + n);
    return dayKey(d);
  }

  function daysBetween(a, b) {
    const da = new Date(`${a}T00:00:00`);
    const db = new Date(`${b}T00:00:00`);
    return Math.round((db - da) / 86400000);
  }

  function agendaDayKeys(events) {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const today = dayKey(now);
    const keys = new Set();
    for (let i = 0; i < 7; i += 1) {
      const d = new Date(now);
      d.setDate(d.getDate() + i);
      keys.add(dayKey(d));
    }
    for (const ev of events) {
      if (ev.layer !== "personal") continue;
      const day = new Date(ev.start);
      day.setHours(0, 0, 0, 0);
      if (day >= now) keys.add(dayKey(day));
    }
    const focus = state.focusDay;
    if (focus && focus >= today) keys.add(focus);
    const sorted = [...keys].sort();
    return sorted.length ? sorted : [today];
  }

  function renderAgenda(events) {
    const el = $("agenda");
    if (!el) return;
    const today = dayKey(new Date());
    const personal = (events || [])
      .filter((e) => e.layer === "personal")
      .sort((a, b) => a.start - b.start);
    const byDay = new Map();
    for (const ev of personal) {
      const key = dayKey(ev.start);
      if (!byDay.has(key)) byDay.set(key, []);
      byDay.get(key).push(ev);
    }
    el.innerHTML = agendaDayKeys(personal)
      .map((key) => {
        const dummy = new Date(`${key}T00:00:00`);
        const meta = formatDayLabel(dummy, today);
        const items = byDay.get(key) || [];
        const rows = items
          .map((ev) => {
            const series = ev.seriesId || ev.uid;
            const hm = formatHM(ev.start);
            const urg = !ev.done ? personalUrgency(ev.start) : "";
            const weekly = ev.repeat === "weekly" ? " · 每周" : "";
            return `<div class="task-card ${urg} ${ev.done ? "is-done" : ""}" draggable="true" data-id="${esc(series)}" data-day="${esc(key)}">
              <div class="task-when">
                <input type="date" class="task-date" value="${esc(key)}" data-date-id="${esc(series)}" data-from-day="${esc(key)}" />
                <input type="time" class="task-time" value="${esc(hm)}" data-time-id="${esc(series)}" />
              </div>
              <div class="task-main">
                <input type="text" class="task-title" maxlength="80" value="${esc(ev.title)}" data-title-id="${esc(series)}" />
                ${ev.note ? `<div class="task-note">${esc(ev.note)}${weekly}</div>` : (weekly ? `<div class="task-note">${weekly.trim()}</div>` : "")}
              </div>
              <div class="task-actions">
                <button type="button" class="task-btn done-btn ${ev.done ? "is-on" : ""}" data-done="${esc(series)}" data-day="${esc(key)}" title="${ev.done ? "撤销完成" : "完成"}">${ev.done ? "✓" : ""}</button>
                <button type="button" class="task-btn del-btn" data-del="${esc(series)}" title="删除">×</button>
              </div>
            </div>`;
          })
          .join("");
        const composer = (items.length || key === today || key === state.focusDay)
          ? `<form class="task-composer" data-day="${esc(key)}">
            <input type="time" name="time" value="09:00" class="task-time" />
            <input type="text" name="title" maxlength="80" placeholder="写点什么…（回车或失焦保存）" />
            <label class="check"><input type="checkbox" name="weekly" /> 每周</label>
            <button type="submit" class="btn-tiny">添加</button>
          </form>`
          : `<div class="day-drop-hint">拖到这一天</div>`;
        return `<div class="day-group ${items.length ? "" : "is-empty"}" data-day="${esc(key)}">
          <div class="day-label ${meta.isToday ? "is-today" : ""}">${esc(meta.label)}${meta.isToday ? " · 今天" : ""}</div>
          ${rows}
          ${composer}
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

  function monthCursor() {
    if (!state.monthCursor) {
      const now = new Date();
      state.monthCursor = new Date(now.getFullYear(), now.getMonth(), 1);
    }
    return state.monthCursor;
  }

  function renderMonth(events) {
    const el = $("cal-month");
    const label = $("month-label");
    if (!el) return;
    const cur = monthCursor();
    const y = cur.getFullYear();
    const m = cur.getMonth();
    if (label) label.textContent = `${y}年${m + 1}月`;
    const first = new Date(y, m, 1);
    const startPad = first.getDay();
    const daysIn = new Date(y, m + 1, 0).getDate();
    const today = dayKey(new Date());
    const byDay = new Map();
    for (const ev of events || []) {
      if (ev.layer !== "personal" || ev.done) continue;
      const key = dayKey(ev.start);
      const bag = byDay.get(key) || { count: 0, due: 0, soon: 0 };
      bag.count += 1;
      const urg = personalUrgency(ev.start);
      if (urg === "due-0") bag.due += 1;
      else if (urg === "due-2") bag.soon += 1;
      byDay.set(key, bag);
    }
    const dows = ["日", "一", "二", "三", "四", "五", "六"]
      .map((d) => `<div class="month-dow">${d}</div>`)
      .join("");
    const cells = [];
    for (let i = 0; i < startPad; i += 1) {
      cells.push(`<div class="month-cell out"></div>`);
    }
    for (let d = 1; d <= daysIn; d += 1) {
      const key = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const bag = byDay.get(key);
      const mark = bag && bag.count
        ? `<span class="month-mark">${bag.count > 1 ? bag.count : "•"}</span>`
        : `<span class="month-mark is-empty"></span>`;
      const cls = [
        "month-cell",
        key === today ? "is-today" : "",
        key === state.focusDay ? "is-focus" : "",
        bag && bag.due ? "has-due" : "",
        bag && !bag.due && bag.soon ? "has-soon" : "",
        bag && bag.count && !bag.due && !bag.soon ? "has-personal" : "",
      ].filter(Boolean).join(" ");
      cells.push(`<button type="button" class="${cls}" data-jump="${key}"><span>${d}</span>${mark}</button>`);
    }
    el.innerHTML = dows + cells.join("");
  }

  function renderMessages(list, targetId, tone) {
    const el = $(targetId);
    if (!el) return;
    const items = Array.isArray(list) ? list : [];
    if (!items.length) {
      el.innerHTML = `<div class="empty">暂无</div>`;
      return;
    }
    const cap = tone === "pending" || tone === "alert" ? 24 : 8;
    el.innerHTML = items
      .slice(0, cap)
      .map(
        (m) => `<article class="msg ${tone || ""}">
        <div class="msg-body">
          <div class="msg-title">${esc(m.title || "留言")}</div>
          <div class="msg-meta">${esc(m.time_text || m.time || "")}</div>
          ${m.text ? `<div class="msg-text">${esc(m.text)}</div>` : ""}
        </div>
        ${m.dismissable && tone === "pending"
          ? `<button type="button" class="pending-remove" data-pending="${esc(m.text)}">撤掉</button>`
          : ""}
      </article>`,
      )
      .join("");
  }

  function applyMessages(messages) {
    state.messages = messages;
    renderMessages((messages && messages.latest) || [], "messages-latest", "");
    renderMessages((messages && messages.pending) || [], "messages-pending", "pending");
    renderMessages((messages && messages.alerts) || [], "messages-alerts", "alert");
    $("msg-count").textContent = String(((messages && messages.latest) || []).length);
    $("pending-count").textContent = String(((messages && messages.pending) || []).length);
    $("alert-count").textContent = String(((messages && messages.alerts) || []).length);
  }

  function setPendingStatus(text) {
    const el = $("pending-status");
    if (el) el.textContent = text;
  }

  async function addPending(text) {
    const res = await fetch("/api/pending", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 404) {
      throw new Error("写入接口不存在：请重启 3100 的 console serve，再 Ctrl+F5");
    }
    if (!res.ok) throw new Error(data.error || "待决写入失败");
    applyMessages(data);
  }

  async function dismissPending(text) {
    const res = await fetch(`/api/pending?text=${encodeURIComponent(text)}`, {
      method: "DELETE",
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 404) {
      throw new Error("撤掉接口不存在：请重启 3100 的 console serve，再 Ctrl+F5");
    }
    if (!res.ok) throw new Error(data.error || "待决删除失败");
    applyMessages(data);
  }

  function personalUrgency(start) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const day = new Date(start);
    day.setHours(0, 0, 0, 0);
    const days = Math.round((day - today) / 86400000);
    if (days < 0) return "past";
    if (days === 0) return "due-0";
    if (days <= 2) return "due-2";
    if (days <= 7) return "due-7";
    return "";
  }

  function arxivAbs(id) {
    return `https://arxiv.org/abs/${encodeURIComponent(id)}`;
  }

  function arxivPdf(id) {
    return `https://arxiv.org/pdf/${encodeURIComponent(id)}`;
  }

  function linkifyDigest(text) {
    const re = /(\d{4}\.\d{4,5}(?:v\d+)?)/g;
    let out = "";
    let last = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      out += esc(text.slice(last, m.index));
      const id = m[1];
      out += `<a href="${arxivAbs(id)}" target="_blank" rel="noopener">${esc(id)}</a>`;
      last = m.index + id.length;
    }
    out += esc(text.slice(last));
    return out;
  }

  function radarHistory(radar) {
    const incoming = radar && Array.isArray(radar.history) ? radar.history : [];
    if (incoming.length) return incoming;
    const prev = state.radar && Array.isArray(state.radar.history) ? state.radar.history : [];
    return prev;
  }

  function renderRadarHistory(hist, activeDate) {
    const history = $("radar-history");
    if (!history) return;
    if (!hist.length) {
      history.innerHTML = `<div class="empty">仅当前一期</div>`;
      return;
    }
    history.innerHTML = hist
      .slice(0, TASK_CAP)
      .map((h) => {
        const on = h.date === activeDate ? "is-active" : "";
        const miss = h.has_digest ? "" : "no-digest";
        return `<button type="button" class="history-chip ${on} ${miss}" data-radar-date="${esc(h.date)}">${esc(h.date)}${h.has_digest ? "" : " · 无正文"}</button>`;
      })
      .join("");
  }

  function renderRadar(radar) {
    const meta = $("radar-meta");
    const stages = $("radar-stages");
    const top5 = $("radar-top5");
    const digest = $("radar-digest");
    const hist = radarHistory(radar);
    if (radar && hist.length) radar.history = hist;
    if (!radar || !radar.available) {
      if (meta) meta.innerHTML = `<div class="meta-pill">雷达数据不可用</div>`;
      if (stages) stages.innerHTML = `<div class="empty">无阶段数据</div>`;
      if (top5) top5.innerHTML = `<div class="empty">无 Top5</div>`;
      if (digest) digest.textContent = "无日报";
      renderRadarHistory(hist, radar && radar.date);
      return;
    }

    const val = radar.validation;
    const valText = val == null
      ? "—"
      : (typeof val === "object"
        ? (val.status || val.result || "有报告")
        : String(val));
    meta.innerHTML = [
      ["日期", radar.date || "—"],
      ["模式", radar.mode || "—"],
      ["校验", valText],
    ]
      .map(
        ([k, v]) =>
          `<div class="meta-pill">${esc(k)} <strong>${esc(v)}</strong></div>`,
      )
      .join("");

    renderRadarHistory(hist, radar.date);

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
            const id = t.id || "";
            const abs = t.abs_url || (id ? arxivAbs(id) : "");
            const pdf = t.pdf_url || (id ? arxivPdf(id) : "");
            const titleHtml = abs
              ? `<a class="top-title" href="${esc(abs)}" target="_blank" rel="noopener">${esc(t.title || "—")}</a>`
              : `<div class="top-title">${esc(t.title || "—")}</div>`;
            const idHtml = id
              ? `<div class="top-id"><a href="${esc(abs)}" target="_blank" rel="noopener">${esc(id)}</a>${pdf ? ` · <a href="${esc(pdf)}" target="_blank" rel="noopener">PDF</a>` : ""}</div>`
              : "";
            return `<div class="top-item">
              <div class="top-rank">${String(i + 1).padStart(2, "0")}</div>
              <div>
                ${titleHtml}
                ${idHtml}
              </div>
              <div class="top-score">${esc(score)}</div>
              <div class="top-bar"><span style="width:${pct}%"></span></div>
            </div>`;
          })
          .join("")
      : `<div class="empty">无 Top5</div>`;

    digest.innerHTML = radar.digest_txt
      ? linkifyDigest(radar.digest_txt)
      : "无日报正文";
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

  function mergeTaskRows(status) {
    const rank = { running: 3, queued: 2, hung: 1, done: 0 };
    const map = new Map();
    const take = (item) => {
      const name = item.slug || item.task || item.id || "";
      if (!name) return;
      const key = String(name).toLowerCase();
      const rec = {
        name,
        status: item.status || "unknown",
        bucket: taskBucket(item),
        attempt: item.attempt,
        time: item.time_text || formatStamp(item.started_at),
        error: item.error || "",
      };
      const prev = map.get(key);
      if (!prev || rank[rec.bucket] > rank[prev.bucket]) map.set(key, rec);
      else if (prev && rec.attempt != null && prev.attempt == null) {
        prev.attempt = rec.attempt;
        if (!prev.time || prev.time === "—") prev.time = rec.time;
      }
    };
    for (const t of (status && status.recent_tasks) || []) take(t);
    for (const a of (status && status.attempts) || []) take(a);
    const rows = [...map.values()];
    rows.sort((a, b) => String(b.time || "").localeCompare(String(a.time || "")));
    const has = (bucket) => rows.some((r) => r.bucket === bucket);
    const queueLen = Number(status && status.queue_len) || 0;
    const active = Number(status && status.active_tasks) || 0;
    if (queueLen > 0 && !has("queued")) {
      rows.push({
        name: `队列 ${queueLen} 项`,
        status: "queued",
        bucket: "queued",
        time: "监控未给卡明细",
      });
    }
    if (active > 0 && !has("running")) {
      rows.push({
        name: `活动 ${active} 项`,
        status: "running",
        bucket: "running",
        time: "监控未给卡明细",
      });
    }
    return rows;
  }

  const TASK_CAP = 10;

  function renderTaskBucket(targetId, countId, items, emptyText) {
    const labelOf = (row) => BUCKET_LABEL[row.bucket] || row.status || "—";
    const shown = items.slice(0, TASK_CAP);
    renderRows(targetId, shown, (row) => {
      const extra = [
        row.attempt != null ? `attempt ${row.attempt}` : "",
        row.time || "",
        row.error || "",
      ].filter(Boolean).join(" · ");
      return `<div class="row">
        <div class="row-main" title="${esc(row.name)}">${esc(row.name)}</div>
        <span class="badge ${badgeClass(row.bucket)}">${esc(labelOf(row))}</span>
        ${extra ? `<div class="row-sub">${esc(extra)}</div>` : ""}
      </div>`;
    });
    const countEl = $(countId);
    if (countEl) countEl.textContent = String(items.length);
    const el = $(targetId);
    if (!items.length) {
      if (el) el.innerHTML = `<div class="empty">${esc(emptyText)}</div>`;
      return;
    }
    if (el && items.length > TASK_CAP) {
      el.insertAdjacentHTML(
        "beforeend",
        `<div class="empty">只列最近 ${TASK_CAP} 条，另有 ${items.length - TASK_CAP} 条</div>`,
      );
    }
  }

  function renderTasks(status) {
    const rows = mergeTaskRows(status);
    renderTaskBucket("tasks-queued", "queued-count", rows.filter((r) => r.bucket === "queued"), "无排队");
    renderTaskBucket("tasks-running", "running-count", rows.filter((r) => r.bucket === "running"), "无运行中");
    renderTaskBucket("tasks-done", "done-count", rows.filter((r) => r.bucket === "done"), "无完成记录");
    renderTaskBucket("tasks-hung", "hung-count", rows.filter((r) => r.bucket === "hung"), "无挂起");

    const experiments =
      (status && status.experiments && status.experiments.cards) || [];
    const expAvailable =
      status && status.experiments && status.experiments.available;
    const expEl = $("experiments");
    if (!expEl) return;
    if (!expAvailable) {
      expEl.innerHTML = `<div class="empty">实验卡目录未初始化</div>`;
    } else {
      const cards = experiments.slice(0, TASK_CAP);
      renderRows("experiments", cards, (c) => {
        const st = c.status || "—";
        return `<div class="row">
          <div class="row-main" title="${esc(c.id || "")}">${esc(c.id || "—")}</div>
          <span class="badge ${badgeClass(st)}">${esc(st)}</span>
        </div>`;
      });
      if (experiments.length > TASK_CAP) {
        expEl.insertAdjacentHTML(
          "beforeend",
          `<div class="empty">只列 ${TASK_CAP} 张，另有 ${experiments.length - TASK_CAP} 张</div>`,
        );
      }
    }
  }

  function renderSystem(status) {
    const devices = $("devices");
    if (!status) {
      devices.innerHTML = `<div class="empty">无状态</div>`;
      return;
    }
    const cards = [
      { name: "RK3528", state: status.broker || status["4b"], detail: "orchestra reporter" },
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
    if (reason === "no_token") {
      el.textContent =
        "未配置 ORCHESTRA_MONITOR_TOKEN：核桃派 usage-monitor 可达但未鉴权，RK3528/核桃派状态无法刷新。在用户环境变量里设好后重新登录（计划任务才能读到），再跑一次 refresh。";
    } else {
      el.textContent = `降级运行：${reason}（设备区可能离线，其余模块继续展示本地缓存）`;
    }
  }

  function renderSoon(status) {
    const el = $("soon");
    if (!el) return;
    const list = upcomingFromEvents(state.events);
    const fallback = (status && status.upcoming_personal) || [];
    const rows = list.length ? list : fallback;
    if (!rows.length) {
      el.classList.add("hidden");
      el.innerHTML = "";
      return;
    }
    el.classList.remove("hidden");
    el.innerHTML = rows
      .slice(0, 4)
      .map((u) => {
        const note = u.note ? ` · ${esc(u.note)}` : "";
        return `<div class="soon-item ${esc(u.urgency || "")}">临近 · ${esc(u.title)} · ${esc(u.in_text)}（${esc(u.at)}）${note}</div>`;
      })
      .join("");
  }

  function renderAll() {
    const { status, radar, messages, events } = state;
    renderBanner(status);
    renderSoon(status);
    renderLivebar(status);
    renderPulse("pulse", status);
    renderPulse("tasks-pulse", status);
    renderAgenda(events);
    renderMonth(events);
    applyMessages(messages);
    renderRadar(radar);
    renderTasks(status);
    renderSystem(status);
    $("foot-gen").textContent = status && status.generated_text
      ? `生成 ${status.generated_text}`
      : "—";
  }

  async function loadCore() {
    const [status, radar, messages, systemIcs, personalIcs, personalApi] = await Promise.all([
      fetchJson("/status.json"),
      fetchJson("/radar.json"),
      fetchJson("/messages.json"),
      fetchText("/system.ics"),
      fetchText("/personal.ics"),
      fetchJson("/api/personal").catch(() => ({ personal: [] })),
    ]);
    state.status = status;
    state.radar = radar;
    state.messages = messages;
    state.personal = personalApi.personal || [];
    state.events = [
      ...parseIcs(systemIcs, "system"),
      ...parseIcs(personalIcs, "personal"),
    ];
    renderAll();
  }

  async function loadMessagesOnly() {
    applyMessages(await fetchJson("/messages.json"));
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

  function setFormStatus(text) {
    const el = $("agenda-status");
    if (el) el.textContent = text || "点月历某天添加 · 卡片可改日期";
  }

  function itemPayload(item, patch) {
    return {
      id: item.id,
      date: item.date,
      time: item.time,
      title: item.title,
      note: item.note || "",
      repeat: item.repeat || "",
      ...(patch || {}),
    };
  }

  async function putPersonal(payload) {
    const res = await fetch("/api/personal", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `失败 ${res.status}`);
    await loadCore();
  }

  async function addPersonal(payload) {
    const res = await fetch("/api/personal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `失败 ${res.status}`);
    await loadCore();
  }

  async function saveQuickAdd(form) {
    const title = (form.title.value || "").trim();
    if (!title) {
      setFormStatus("标题必填");
      return;
    }
    if (form.dataset.busy === "1") return;
    form.dataset.busy = "1";
    setFormStatus("保存中…");
    try {
      state.focusDay = form.dataset.day;
      await addPersonal({
        date: form.dataset.day,
        time: form.time.value || "09:00",
        title,
        note: "",
        repeat: form.weekly.checked ? "weekly" : "",
      });
      setFormStatus("已保存");
    } finally {
      delete form.dataset.busy;
    }
  }

  async function patchField(id, patch) {
    const item = state.personal.find((p) => p.id === id);
    if (!item) return;
    setFormStatus("保存中…");
    await putPersonal(itemPayload(item, patch));
    setFormStatus("已保存");
  }

  async function moveCard(id, fromDay, toDay) {
    if (!id || !toDay || fromDay === toDay) return;
    const item = state.personal.find((p) => p.id === id);
    if (!item) return;
    const date = item.repeat === "weekly"
      ? addDaysISO(item.date, daysBetween(fromDay, toDay))
      : toDay;
    setFormStatus("保存中…");
    state.focusDay = toDay;
    await putPersonal(itemPayload(item, { date }));
    setFormStatus("已改日期");
  }

  async function deletePersonal(id) {
    if (!id) return;
    const item = state.personal.find((p) => p.id === id);
    const msg = item && item.repeat === "weekly"
      ? "删除整个每周系列？"
      : "删除这条个人日程？";
    if (!window.confirm(msg)) return;
    const res = await fetch(`/api/personal?id=${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setFormStatus(data.error || `删除失败 ${res.status}`);
      return;
    }
    setFormStatus("已删除");
    await loadCore();
  }

  async function toggleDone(id, day) {
    if (!id) return;
    const res = await fetch("/api/personal/done", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, date: day || undefined }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setFormStatus(data.error || `完成失败 ${res.status}`);
      return;
    }
    await loadCore();
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
    const pendingForm = $("pending-composer");
    const pendingInput = $("pending-input");
    const pendingAdd = $("pending-add");
    const savePending = () => {
      const text = (pendingInput && pendingInput.value || "").trim();
      if (!text) {
        setPendingStatus("先在框里写一句话，再点写入");
        if (pendingInput) pendingInput.focus();
        return;
      }
      addPending(text)
        .then(() => {
          pendingInput.value = "";
          setPendingStatus("已写入。办完后点右侧「撤掉」。");
          pendingInput.focus();
        })
        .catch((err) => setPendingStatus(err.message));
    };
    if (pendingForm) {
      pendingForm.addEventListener("submit", (e) => {
        e.preventDefault();
        savePending();
      });
    }
    if (pendingAdd) {
      pendingAdd.addEventListener("click", (e) => {
        e.preventDefault();
        savePending();
      });
    }
    const pendingList = $("messages-pending");
    if (pendingList) {
      pendingList.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-pending]");
        if (!btn) return;
        dismissPending(btn.dataset.pending).catch((err) => setFormStatus(err.message));
      });
    }
    $("agenda").addEventListener("click", (e) => {
      const del = e.target.closest("[data-del]");
      const done = e.target.closest("[data-done]");
      if (done) {
        toggleDone(done.dataset.done, done.dataset.day).catch((err) => setFormStatus(err.message));
      } else if (del) {
        deletePersonal(del.dataset.del).catch((err) => setFormStatus(err.message));
      }
    });
    $("agenda").addEventListener("change", (e) => {
      const timeEl = e.target.closest("[data-time-id]");
      const dateEl = e.target.closest("[data-date-id]");
      if (dateEl) {
        moveCard(dateEl.dataset.dateId, dateEl.dataset.fromDay, dateEl.value)
          .catch((err) => setFormStatus(err.message));
      } else if (timeEl) {
        patchField(timeEl.dataset.timeId, { time: timeEl.value }).catch((err) => setFormStatus(err.message));
      }
    });
    $("agenda").addEventListener("focusout", (e) => {
      const composer = e.target.closest(".task-composer");
      if (composer && e.target.name === "title") {
        const next = (e.relatedTarget && composer.contains(e.relatedTarget));
        if (next) return;
        if ((composer.title.value || "").trim()) {
          saveQuickAdd(composer).catch((err) => setFormStatus(err.message));
        }
        return;
      }
      const titleEl = e.target.closest("[data-title-id]");
      if (!titleEl) return;
      const item = state.personal.find((p) => p.id === titleEl.dataset.titleId);
      const next = titleEl.value.trim();
      if (!item || !next || next === item.title) return;
      patchField(item.id, { title: next }).catch((err) => setFormStatus(err.message));
    });
    $("agenda").addEventListener("submit", (e) => {
      const form = e.target.closest(".task-composer");
      if (!form) return;
      e.preventDefault();
      saveQuickAdd(form).catch((err) => setFormStatus(err.message));
    });
    $("agenda").addEventListener("dragstart", (e) => {
      const card = e.target.closest(".task-card");
      if (!card || e.target.closest("input,button")) {
        e.preventDefault();
        return;
      }
      e.dataTransfer.setData("text/plain", JSON.stringify({
        id: card.dataset.id,
        day: card.dataset.day,
      }));
      e.dataTransfer.effectAllowed = "move";
    });
    $("agenda").addEventListener("dragover", (e) => {
      const group = e.target.closest(".day-group");
      if (!group) return;
      e.preventDefault();
      group.classList.add("is-over");
    });
    $("agenda").addEventListener("dragleave", (e) => {
      const group = e.target.closest(".day-group");
      if (group && !group.contains(e.relatedTarget)) group.classList.remove("is-over");
    });
    $("agenda").addEventListener("drop", (e) => {
      const group = e.target.closest(".day-group");
      if (!group) return;
      e.preventDefault();
      group.classList.remove("is-over");
      let payload;
      try {
        payload = JSON.parse(e.dataTransfer.getData("text/plain") || "{}");
      } catch (err) {
        return;
      }
      moveCard(payload.id, payload.day, group.dataset.day).catch((err) => setFormStatus(err.message));
    });
    $("month-prev").addEventListener("click", () => {
      const cur = monthCursor();
      state.monthCursor = new Date(cur.getFullYear(), cur.getMonth() - 1, 1);
      renderMonth(state.events);
    });
    $("month-next").addEventListener("click", () => {
      const cur = monthCursor();
      state.monthCursor = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
      renderMonth(state.events);
    });
    $("cal-month").addEventListener("click", (e) => {
      const cell = e.target.closest("[data-jump]");
      if (!cell) return;
      const jump = cell.dataset.jump;
      const today = dayKey(new Date());
      state.focusDay = jump;
      if (jump >= today) {
        renderAgenda(state.events);
        setFormStatus(`添加：${jump} · 或改卡片上的日期`);
      }
      renderMonth(state.events);
      const group = document.querySelector(`.day-group[data-day="${jump}"]`);
      if (group) group.scrollIntoView({ block: "start", behavior: "smooth" });
    });
    $("radar-history").addEventListener("click", (e) => {
      const chip = e.target.closest("[data-radar-date]");
      if (!chip) return;
      fetchJson(`/api/radar?date=${encodeURIComponent(chip.dataset.radarDate)}`)
        .then((radar) => {
          if (!radar.history || !radar.history.length) {
            radar.history = (state.radar && state.radar.history) || [];
          }
          state.radar = radar;
          renderRadar(radar);
        })
        .catch((err) => {
          $("banner").classList.remove("hidden");
          $("banner").textContent = `切换日报失败：${err.message}`;
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
