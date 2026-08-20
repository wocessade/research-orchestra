import unittest
from datetime import date, datetime, timedelta

from feed_schedule import (
    Event,
    add_personal,
    build_ics,
    delete_personal,
    dump_schedule,
    expand_personal,
    expand_system,
    next_system_events,
    parse_schedule,
    toggle_personal_done,
    upcoming_personal,
    update_personal,
)

GOOD = """
[system]
radar = "23:30"
cold_backup = "03:00"
nas_backup = "04:17"
housekeeping = { time = "04:00", dow = "sun" }

[[personal]]
date = "2026-09-01"
time = "09:00"
title = "开学报到"
note = "宿舍-实验室互通实测待办"
"""


class ParseScheduleTest(unittest.TestCase):
    def test_parse_valid(self):
        sched = parse_schedule(GOOD)
        self.assertEqual(set(sched["system"]), {"radar", "cold_backup", "nas_backup", "housekeeping"})
        self.assertEqual(sched["personal"][0]["title"], "开学报到")

    def test_parse_invalid_toml(self):
        with self.assertRaises(ValueError):
            parse_schedule("[system\nradar = ")

    def test_parse_unknown_system_key(self):
        with self.assertRaises(ValueError):
            parse_schedule('[system]\nfoo = "01:00"')

    def test_parse_bad_personal_time(self):
        with self.assertRaises(ValueError):
            parse_schedule('[[personal]]\ndate = "2026-09-01"\ntime = "25:00"\ntitle = "x"')

    def test_parse_bad_housekeeping(self):
        with self.assertRaises(ValueError):
            parse_schedule('[system]\nhousekeeping = { time = "04:00", dow = "foo" }')


class ExpandSystemTest(unittest.TestCase):
    def test_daily_events(self):
        sched = parse_schedule(GOOD)
        # 窗口 08-20(周四)~08-22(周六)，不含周日 → housekeeping 不参与计数
        events = expand_system(sched["system"], date(2026, 8, 20), date(2026, 8, 22))
        self.assertEqual(len(events), 9)  # 3 个每日项 × 3 天
        radar = [e for e in events if e.summary == "夜间雷达"]
        self.assertTrue(all(e.start.hour == 23 and e.start.minute == 30 for e in radar))
        self.assertTrue(all((e.end - e.start) == timedelta(minutes=30) for e in events))

    def test_weekly_housekeeping(self):
        sched = parse_schedule(GOOD)
        events = expand_system(sched["system"], date(2026, 8, 20), date(2026, 9, 16))
        hs = [e for e in events if e.summary == "周日整理"]
        self.assertEqual(len(hs), 4)
        self.assertTrue(all(e.start.weekday() == 6 for e in hs))

    def test_window_bounds(self):
        sched = parse_schedule(GOOD)
        start, end = date(2026, 8, 20), date(2026, 8, 22)
        events = expand_system(sched["system"], start, end)
        self.assertTrue(all(start <= e.start.date() <= end for e in events))


class ExpandPersonalTest(unittest.TestCase):
    def test_inside_window(self):
        sched = parse_schedule(GOOD)
        events = expand_personal(sched["personal"], date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].summary, "开学报到")

    def test_outside_window_skipped(self):
        sched = parse_schedule(GOOD)
        events = expand_personal(sched["personal"], date(2026, 10, 1), date(2026, 10, 30))
        self.assertEqual(events, [])


class BuildIcsTest(unittest.TestCase):
    def test_structure_and_escaping(self):
        ev = Event(datetime(2026, 8, 20, 23, 30), datetime(2026, 8, 20, 23, 45),
                   "夜间雷达;测试,项", "sys-radar-20260820")
        ics = build_ics([ev], "System")
        self.assertIn("BEGIN:VCALENDAR", ics)
        self.assertIn("BEGIN:VEVENT", ics)
        self.assertIn("DTSTART:20260820T233000", ics)
        self.assertIn("DTEND:20260820T234500", ics)
        self.assertIn("SUMMARY:夜间雷达\\;测试\\,项", ics)
        self.assertTrue(ics.endswith("END:VCALENDAR\r\n"))

    def test_events_sorted(self):
        e1 = Event(datetime(2026, 8, 21, 9, 0), datetime(2026, 8, 21, 9, 30), "晚", "u1")
        e2 = Event(datetime(2026, 8, 20, 9, 0), datetime(2026, 8, 20, 9, 30), "早", "u2")
        ics = build_ics([e1, e2], "P")
        self.assertLess(ics.index("早"), ics.index("晚"))


class NextSystemEventsTest(unittest.TestCase):
    def test_afternoon_now(self):
        sched = parse_schedule(GOOD)
        now = datetime(2026, 8, 20, 12, 0)
        nxt = next_system_events(sched["system"], now)
        self.assertEqual([n["label"] for n in nxt][:3], ["雷达", "冷备到核桃派", "NAS 盘内备份"])
        self.assertEqual(nxt[0]["at"], datetime(2026, 8, 20, 23, 30))

    def test_after_midnight(self):
        sched = parse_schedule(GOOD)
        now = datetime(2026, 8, 20, 23, 45)
        nxt = next_system_events(sched["system"], now)
        self.assertEqual(nxt[0]["at"], datetime(2026, 8, 21, 3, 0))


class UpcomingPersonalTest(unittest.TestCase):
    def test_includes_today_and_excludes_past_and_done(self):
        sched = parse_schedule(GOOD)
        sched = add_personal(sched, {
            "date": "2026-08-20", "time": "08:00", "title": "已过",
        })
        sched = add_personal(sched, {
            "date": "2026-08-20", "time": "21:00", "title": "今晚组会",
        })
        nid = [p["id"] for p in sched["personal"] if p["title"] == "今晚组会"][0]
        sched = toggle_personal_done(sched, nid, "2026-08-20")
        now = datetime(2026, 8, 20, 12, 0)
        rows = upcoming_personal(sched["personal"], now, days=14)
        titles = [r["title"] for r in rows]
        self.assertIn("开学报到", titles)
        self.assertNotIn("已过", titles)
        self.assertNotIn("今晚组会", titles)
        school = [r for r in rows if r["title"] == "开学报到"][0]
        self.assertEqual(school["days_left"], 12)
        self.assertEqual(school["in_text"], "12 天后")

    def test_horizon_cuts_off(self):
        sched = parse_schedule(GOOD)
        now = datetime(2026, 8, 20, 12, 0)
        self.assertEqual(upcoming_personal(sched["personal"], now, days=7), [])
        self.assertEqual(
            [r["title"] for r in upcoming_personal(sched["personal"], now, days=14)],
            ["开学报到"],
        )

    def test_empty_personal(self):
        self.assertEqual(upcoming_personal([], datetime(2026, 8, 20, 12, 0)), [])


class PersonalCrudTest(unittest.TestCase):
    def test_dump_roundtrip_preserves_system(self):
        sched = parse_schedule(GOOD)
        again = parse_schedule(dump_schedule(sched))
        self.assertEqual(again["system"]["radar"], "23:30")
        self.assertEqual(again["system"]["housekeeping"]["dow"], "sun")
        self.assertEqual(again["personal"][0]["title"], "开学报到")
        self.assertEqual(again["personal"][0]["id"], sched["personal"][0]["id"])

    def test_add_update_delete(self):
        sched = parse_schedule(GOOD)
        system_radar = sched["system"]["radar"]
        sched = add_personal(sched, {
            "date": "2026-09-02", "time": "14:00", "title": "组会", "note": "实验室",
        })
        self.assertEqual(len(sched["personal"]), 2)
        self.assertEqual(sched["system"]["radar"], system_radar)
        nid = [p["id"] for p in sched["personal"] if p["title"] == "组会"][0]
        sched = update_personal(sched, nid, {
            "date": "2026-09-02", "time": "15:30", "title": "组会改期",
        })
        self.assertEqual(sched["personal"][1]["title"], "组会改期")
        self.assertEqual(sched["personal"][1]["time"].hour, 15)
        sched = delete_personal(sched, sched["personal"][1]["id"])
        self.assertEqual(len(sched["personal"]), 1)
        self.assertEqual(sched["personal"][0]["title"], "开学报到")
        with self.assertRaises(KeyError):
            delete_personal(sched, "nope")

    def test_add_rejects_bad_time(self):
        sched = parse_schedule(GOOD)
        with self.assertRaises(ValueError):
            add_personal(sched, {"date": "2026-09-02", "time": "25:00", "title": "x"})

    def test_weekly_expands_and_done_toggle(self):
        sched = parse_schedule(GOOD)
        sched = add_personal(sched, {
            "date": "2026-08-20", "time": "14:00", "title": "组会", "repeat": "weekly",
        })
        item = [p for p in sched["personal"] if p["title"] == "组会"][0]
        events = expand_personal(sched["personal"], date(2026, 8, 20), date(2026, 9, 10))
        weekly = [e for e in events if e.repeat == "weekly"]
        self.assertGreaterEqual(len(weekly), 3)
        self.assertTrue(all(e.start.weekday() == 3 for e in weekly))  # 2026-08-20 周四
        sched = toggle_personal_done(sched, item["id"], "2026-08-20")
        events = expand_personal(sched["personal"], date(2026, 8, 20), date(2026, 8, 20))
        hit = [e for e in events if e.summary == "组会"][0]
        self.assertTrue(hit.done)
        text = dump_schedule(sched)
        self.assertIn('repeat = "weekly"', text)
        self.assertIn("2026-08-20", text)
        again = parse_schedule(text)
        self.assertEqual(again["personal"][1]["repeat"], "weekly")

    def test_oneshot_done_roundtrip(self):
        sched = parse_schedule(GOOD)
        ident = sched["personal"][0]["id"]
        sched = toggle_personal_done(sched, ident)
        self.assertTrue(sched["personal"][0]["done"])
        again = parse_schedule(dump_schedule(sched))
        self.assertTrue(again["personal"][0]["done"])
        ics = build_ics(expand_personal(again["personal"], date(2026, 9, 1), date(2026, 9, 1)), "P")
        self.assertIn("STATUS:COMPLETED", ics)


if __name__ == "__main__":
    unittest.main()
