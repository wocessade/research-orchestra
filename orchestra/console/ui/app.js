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
      { name: "4B", state: status["4b"] || "—" },
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

  function renderPulse(targetId, status) {
    const el = $(targetId);
    if (!el || !status) {
      if (el) el.innerHTML = `<div class="empty">无状态数据</div>`;
      return;
    }
    const upcoming = (status && status.upcoming_personal) || [];
    const soon = upcoming[0];
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

  function renderAgenda(events) {
    const el = $("agenda");
    if (!el) return;
    const now = new Date();
    const today = dayKey(now);
    const start = new Date(now);
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - 3);
    const sysEnd = new Date(now);
    sysEnd.setHours(23, 59, 59, 999);
    sysEnd.setDate(sysEnd.getDate() + 7);
    const perEnd = new Date(now);
    perEnd.setHours(23, 59, 59, 999);
    perEnd.setDate(perEnd.getDate() + 60);

    const filtered = events
      .filter((e) => {
        if (e.start < start) return false;
        return e.layer === "personal" ? e.start <= perEnd : e.start <= sysEnd;
      })
      .sort((a, b) => a.start - b.start);

    if (!filtered.length) {
      el.innerHTML = `<div class="empty">窗口内无日程（系统：昨3天→未7天；个人：未60天）</div>`;
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
          .map((ev) => {
            const series = ev.seriesId || ev.uid;
            const day = dayKey(ev.start);
            const side = ev.layer === "personal"
              ? `<div class="event-side">
                  <span class="event-layer">${ev.repeat === "weekly" ? "每周" : "个人"}</span>
                  <button type="button" class="btn-tiny" data-done="${esc(series)}" data-day="${esc(day)}">${ev.done ? "撤销" : "完成"}</button>
                  <button type="button" class="btn-tiny" data-edit="${esc(series)}">改</button>
                  <button type="button" class="btn-tiny danger" data-del="${esc(series)}">${ev.repeat === "weekly" ? "删系列" : "删"}</button>
                </div>`
              : `<div class="event-layer">系统</div>`;
            const urg = ev.layer === "personal" && !ev.done ? personalUrgency(ev.start) : "";
            const timeCls = ev.layer === "personal" ? "event-time editish" : "event-time";
            const extra = ev.done ? "done" : "";
            return `<div class="event ${urg} ${extra}">
            <div class="${timeCls}" ${ev.layer === "personal" ? `data-edit="${esc(series)}" title="改时间"` : ""}>${esc(formatHM(ev.start))}</div>
            <div class="event-rail ${esc(ev.layer)}"></div>
            <div>
              <div class="event-title">${esc(ev.title)}</div>
              ${ev.note ? `<div class="event-note">${esc(ev.note)}</div>` : ""}
            </div>
            ${side}
          </div>`;
          })
          .join("");
        return `<div class="day-group" data-day="${esc(meta.key)}">
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
        <div class="msg-title">${esc(m.title || "留言")}</div>
        <div class="msg-meta">${esc(m.time_text || m.time || "")}</div>
        ${m.text ? `<div class="msg-text">${esc(m.text)}</div>` : ""}
      </article>`,
      )
      .join("");
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

  function renderRadar(radar) {
    const meta = $("radar-meta");
    const stages = $("radar-stages");
    const top5 = $("radar-top5");
    const digest = $("radar-digest");
    const history = $("radar-history");
    if (!radar || !radar.available) {
      if (meta) meta.innerHTML = `<div class="meta-pill">雷达数据不可用</div>`;
      if (stages) stages.innerHTML = `<div class="empty">无阶段数据</div>`;
      if (top5) top5.innerHTML = `<div class="empty">无 Top5</div>`;
      if (digest) digest.textContent = "无日报";
      if (history) history.innerHTML = `<div class="empty">暂无往期</div>`;
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

    const hist = Array.isArray(radar.history) ? radar.history : [];
    if (history) {
      history.innerHTML = hist.length
        ? hist
            .map((h) => {
              const on = h.date === radar.date ? "is-active" : "";
              const miss = h.has_digest ? "" : "no-digest";
              return `<button type="button" class="history-chip ${on} ${miss}" data-radar-date="${esc(h.date)}">${esc(h.date)}${h.has_digest ? "" : " · 无正文"}</button>`;
            })
            .join("")
        : `<div class="empty">仅当前一期</div>`;
    }

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

  function renderTaskBucket(targetId, countId, items, emptyText) {
    const labelOf = (row) => BUCKET_LABEL[row.bucket] || row.status || "—";
    renderRows(targetId, items, (row) => {
      const extra = [
        row.attempt != null ? `attempt ${row.attempt}` : "",
        row.time || "",
        row.error || "",
      ].filter(Boolean).join(" · ");
      return `<div class="row">
        <div class="row-main">${esc(row.name)}</div>
        <span class="badge ${badgeClass(row.bucket)}">${esc(labelOf(row))}</span>
        ${extra ? `<div class="row-sub">${esc(extra)}</div>` : ""}
      </div>`;
    });
    const countEl = $(countId);
    if (countEl) countEl.textContent = String(items.length);
    if (!items.length) {
      const el = $(targetId);
      if (el) el.innerHTML = `<div class="empty">${esc(emptyText)}</div>`;
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
    if (reason === "no_token") {
      el.textContent =
        "未配置 ORCHESTRA_MONITOR_TOKEN：核桃派 usage-monitor 可达但未鉴权，4B/核桃派状态无法刷新。在用户环境变量里设好后重新登录（计划任务才能读到），再跑一次 refresh。";
    } else {
      el.textContent = `降级运行：${reason}（设备区可能离线，其余模块继续展示本地缓存）`;
    }
  }

  function renderSoon(status) {
    const el = $("soon");
    if (!el) return;
    const list = (status && status.upcoming_personal) || [];
    if (!list.length) {
      el.classList.add("hidden");
      el.innerHTML = "";
      return;
    }
    el.classList.remove("hidden");
    el.innerHTML = list
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

  function setFormStatus(text) {
    $("pf-status").textContent = text || "";
  }

  function resetPersonalForm() {
    state.editingId = "";
    $("pf-id").value = "";
    const now = new Date();
    $("pf-date").value = dayKey(now);
    $("pf-time").value = `${String((now.getHours() + 1) % 24).padStart(2, "0")}:00`;
    $("pf-title").value = "";
    $("pf-note").value = "";
    $("pf-weekly").checked = false;
    $("pf-submit").textContent = "添加";
    $("pf-cancel").classList.add("hidden");
  }

  function fillPersonalForm(item) {
    state.editingId = item.id;
    $("pf-id").value = item.id;
    $("pf-date").value = item.date;
    $("pf-time").value = item.time;
    $("pf-title").value = item.title;
    $("pf-note").value = item.note || "";
    $("pf-weekly").checked = item.repeat === "weekly";
    $("pf-submit").textContent = "保存";
    $("pf-cancel").classList.remove("hidden");
  }

  function formPayload() {
    return {
      date: $("pf-date").value,
      time: $("pf-time").value,
      title: $("pf-title").value.trim(),
      note: $("pf-note").value.trim(),
      repeat: $("pf-weekly").checked ? "weekly" : "",
    };
  }

  async function savePersonal(ev) {
    ev.preventDefault();
    const payload = formPayload();
    if (!payload.title) {
      setFormStatus("标题必填");
      return;
    }
    setFormStatus("保存中…");
    const editing = state.editingId;
    const res = await fetch("/api/personal", {
      method: editing ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(editing ? { ...payload, id: editing } : payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setFormStatus(data.error || `失败 ${res.status}`);
      return;
    }
    resetPersonalForm();
    setFormStatus("已保存");
    await loadCore();
  }

  async function deletePersonal(id) {
    if (!id) return;
    const item = state.personal.find((p) => p.id === id);
    const msg = item && item.repeat === "weekly"
      ? "删除整个每周系列？（系统层事件不会被删）"
      : "删除这条个人日程？系统层事件不会被删。";
    if (!window.confirm(msg)) return;
    const res = await fetch(`/api/personal?id=${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setFormStatus(data.error || `删除失败 ${res.status}`);
      return;
    }
    if (state.editingId === id) resetPersonalForm();
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
    $("personal-form").addEventListener("submit", (e) => {
      savePersonal(e).catch((err) => setFormStatus(err.message));
    });
    $("pf-cancel").addEventListener("click", () => {
      resetPersonalForm();
      setFormStatus("");
    });
    $("agenda").addEventListener("click", (e) => {
      const edit = e.target.closest("[data-edit]");
      const del = e.target.closest("[data-del]");
      const done = e.target.closest("[data-done]");
      if (done) {
        toggleDone(done.dataset.done, done.dataset.day).catch((err) => setFormStatus(err.message));
      } else if (edit) {
        const item = state.personal.find((p) => p.id === edit.dataset.edit);
        if (item) {
          fillPersonalForm(item);
          if (edit.classList.contains("event-time")) $("pf-time").focus();
          else $("pf-title").focus();
        }
      } else if (del) {
        deletePersonal(del.dataset.del).catch((err) => setFormStatus(err.message));
      }
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
      state.focusDay = cell.dataset.jump;
      renderMonth(state.events);
      const group = document.querySelector(`.day-group[data-day="${cell.dataset.jump}"]`);
      if (group) group.scrollIntoView({ block: "start", behavior: "smooth" });
    });
    $("radar-history").addEventListener("click", (e) => {
      const chip = e.target.closest("[data-radar-date]");
      if (!chip) return;
      fetchJson(`/api/radar?date=${encodeURIComponent(chip.dataset.radarDate)}`)
        .then((radar) => {
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
    resetPersonalForm();
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
