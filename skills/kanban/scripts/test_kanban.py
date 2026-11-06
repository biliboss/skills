# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tests of kanban.py: the Upstream clipping, the band's periods, the running stretch, the journal and the CLI.
Run: uv run --script test_kanban.py   (stdlib unittest; temp KANBAN_DIR and COSTS_DIR, invented data; the real journals
are never touched)"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cost-track" / "scripts"))
import kanban as K  # noqa: E402

BRT = timezone(timedelta(hours=-3))
RATE = 50000 / 105  # an investment center: the goal (R$ 50 mil) over 5 h x 21 days, R$ 476,19 per hour


def t(text: str) -> datetime:
    """A local time in the tests' clock: '2026-11-06 10:00'."""
    return datetime.fromisoformat(text).replace(tzinfo=BRT)


def ev(kind: str, card: str, at: str, **value) -> dict:
    return {"id": f"{card}-{at}", "event": kind, "at": t(at).isoformat(), "actor": "test", "card_id": card, "value": value}


def card(card_id="c1", domain="kanban", start="2026-11-06 08:00", stage="Upstream", moves=()) -> K.Card:
    """A card created at `start` in `stage`, then moved: moves = [("2026-11-06 09:00", "Downstream"), ...]."""
    es = [ev("card.created", card_id, start, title=f"Card {card_id}", domain=domain, stage=stage)]
    es += [ev("card.moved", card_id, at, stage=st) for at, st in moves]
    return K.card_from(es)


def entry(start: str, end: str, domain="kanban", center="inv", running=False, eid="e") -> K.TimeEntry:
    return K.TimeEntry(eid, domain, center, t(start), t(end), running)


class ClipTest(unittest.TestCase):
    """A card's money: only its domain's time, only while it was in Upstream, partial overlaps clipped."""

    now = t("2026-11-06 18:00")
    rates = {"inv": RATE}

    def money(self, c, *entries):
        return K.card_money(c, list(entries), self.rates, self.now)

    def test_time_before_upstream_does_not_count(self):
        c = card(start="2026-11-06 10:00")
        m = self.money(c, entry("2026-11-06 09:00", "2026-11-06 09:30"), entry("2026-11-06 09:30", "2026-11-06 10:30"))
        self.assertEqual(m.total.seconds, 1800)  # only 10:00-10:30 of the second entry
        self.assertEqual([(s.start, s.end) for s in m.slices], [(t("2026-11-06 10:00"), t("2026-11-06 10:30"))])

    def test_time_after_leaving_upstream_does_not_count(self):
        c = card(start="2026-11-06 10:00", moves=[("2026-11-06 11:00", "Downstream")])
        m = self.money(c, entry("2026-11-06 10:30", "2026-11-06 11:30"), entry("2026-11-06 12:00", "2026-11-06 13:00"))
        self.assertEqual(m.total.seconds, 1800)  # 10:30-11:00; the rest is Downstream time

    def test_up_down_up_counts_both_upstream_stays_only(self):
        c = card(start="2026-11-06 08:00", moves=[("2026-11-06 09:00", "Downstream"), ("2026-11-06 10:00", "Upstream")])
        m = self.money(c, entry("2026-11-06 08:30", "2026-11-06 10:30", eid="long"),
                       entry("2026-11-06 09:15", "2026-11-06 09:45", eid="between"))
        self.assertEqual(m.total.seconds, 3600)  # 08:30-09:00 and 10:00-10:30; nothing of the Downstream hour
        self.assertEqual([s.entry for s in m.slices], ["long", "long"])
        self.assertEqual(m.card.stage, K.Stage.UPSTREAM)
        self.assertEqual(len(m.card.stays), 3)

    def test_another_domain_does_not_count(self):
        m = self.money(card(), entry("2026-11-06 09:00", "2026-11-06 10:00", domain="dev-console"))
        self.assertEqual(m.total, K.Money(0, 0))

    def test_card_with_no_time(self):
        m = self.money(card())
        self.assertEqual((m.total, m.slices, m.live_rate_hour), (K.Money(0, 0), (), 0.0))

    def test_a_card_that_never_was_in_upstream_has_no_upstream_time(self):
        c = card(stage="Downstream", moves=[("2026-11-06 12:00", "Feito")])
        self.assertEqual(self.money(c, entry("2026-11-06 08:00", "2026-11-06 17:00")).total.seconds, 0)

    def test_priced_at_the_center_rate(self):
        m = self.money(card(), entry("2026-11-06 09:00", "2026-11-06 10:00"))
        self.assertEqual(m.total, K.Money(3600, 476.19))
        self.assertEqual(m.slices[0].rate_hour, RATE)

    def test_unknown_center_counts_the_hours_but_no_money(self):
        m = self.money(card(), entry("2026-11-06 09:00", "2026-11-06 10:00", center="nobody"))
        self.assertEqual(m.total, K.Money(3600, 0.0))

    def test_a_move_to_the_same_stage_changes_nothing(self):
        c = card(moves=[("2026-11-06 09:00", "Upstream")])
        self.assertEqual(len(c.stays), 1)


class StoppedEntryTest(unittest.TestCase):
    """A stopped entry runs from its time_entry.started for its seconds, not back from the moment it was written."""

    def test_idle_trim_keeps_the_real_start(self):
        cost = [
            {"id": "s", "event": "time_entry.started", "cost_center": "inv", "at": t("2026-11-06 10:00").isoformat(),
             "value": {"domain": "kanban"}},
            # stopped for idle at 10:40 with the last 10 idle minutes trimmed: 30 min, 10:00-10:30
            {"id": "x", "event": "time_entry.stopped", "cost_center": "inv", "at": t("2026-11-06 10:40").isoformat(),
             "value": {"domain": "kanban", "seconds": 1800, "rate_hour": RATE, "cost": 238.1, "ended_by": "idle"}},
        ]
        [e] = K.time_entries(cost, None, t("2026-11-06 12:00"))
        self.assertEqual((e.start, e.end, e.center, e.domain), (t("2026-11-06 10:00"), t("2026-11-06 10:30"), "inv", "kanban"))
        m = K.card_money(card(start="2026-11-06 10:20"), [e], {"inv": RATE}, t("2026-11-06 12:00"))
        self.assertEqual(m.total.seconds, 600)  # 10:20-10:30, not 10:20-10:40

    def test_a_stopped_entry_without_its_start_runs_back_from_its_time(self):
        cost = [{"id": "x", "event": "time_entry.stopped", "cost_center": "inv", "at": t("2026-11-06 11:00").isoformat(),
                 "value": {"domain": "kanban", "seconds": 600}}]
        [e] = K.time_entries(cost, None, t("2026-11-06 12:00"))
        self.assertEqual((e.start, e.end), (t("2026-11-06 10:50"), t("2026-11-06 11:00")))


class RunningTest(unittest.TestCase):
    """The stretch running now counts until now and makes the card and the band live."""

    now = t("2026-11-06 12:00")

    def run_(self, started="2026-11-06 11:30", seen_s_ago=5, domain="kanban"):
        return {"center": "inv", "domain": domain, "started_at": t(started).isoformat(),
                "last_seen": (self.now - timedelta(seconds=seen_s_ago)).isoformat(), "rate_hour": RATE}

    def test_running_counts_until_now_and_ticks(self):
        entries = K.time_entries([], self.run_(), self.now)
        self.assertTrue(entries[0].running)
        c = card(start="2026-11-06 10:00")
        m = K.card_money(c, entries, {"inv": RATE}, self.now)
        self.assertEqual((m.total.seconds, m.live_rate_hour), (1800, RATE))
        self.assertTrue(m.slices[0].running)
        tot = K.upstream_totals([c], entries, {"inv": RATE}, self.now)
        self.assertEqual((tot.today.seconds, tot.live_rate_hour, tot.live_domain, tot.at), (1800, RATE, "kanban", self.now))

    def test_running_on_a_card_out_of_upstream_does_not_tick(self):
        c = card(start="2026-11-06 10:00", moves=[("2026-11-06 11:45", "Downstream")])
        entries = K.time_entries([], self.run_(), self.now)
        m = K.card_money(c, entries, {"inv": RATE}, self.now)
        self.assertEqual((m.total.seconds, m.live_rate_hour), (900, 0.0))  # 11:30-11:45 only
        self.assertEqual(K.upstream_totals([c], entries, {"inv": RATE}, self.now).live_rate_hour, 0.0)

    def test_running_on_another_domain_does_not_tick(self):
        entries = K.time_entries([], self.run_(domain="tasks"), self.now)
        self.assertEqual(K.upstream_totals([card()], entries, {"inv": RATE}, self.now).live_rate_hour, 0.0)

    def test_a_stale_stretch_ended_at_its_last_ping(self):
        [e] = K.time_entries([], self.run_(seen_s_ago=120), self.now)
        self.assertFalse(e.running)
        self.assertEqual(e.end, self.now - timedelta(seconds=120))


class PeriodsTest(unittest.TestCase):
    """Hoje, Semana (from Monday) and Mês (from the 1st), each cut at its own midnight."""

    rates = {"inv": RATE}

    def totals(self, now, *entries):
        c = card(start="2026-10-01 00:00")  # in Upstream for the whole test
        return K.upstream_totals([c], list(entries), self.rates, t(now))

    def test_periods_start_on_monday_and_on_the_first(self):
        day, week, month = K.periods(t("2026-11-06 12:00"))  # a Friday
        self.assertEqual((day, week, month), (t("2026-11-06 00:00"), t("2026-11-02 00:00"), t("2026-11-01 00:00")))
        self.assertEqual(K.periods(t("2026-11-02 09:00"))[1], t("2026-11-02 00:00"))  # a Monday is its own week start

    def test_monday_start(self):
        tot = self.totals("2026-11-06 12:00",
                          entry("2026-11-01 10:00", "2026-11-01 11:00"),  # Sunday: the month, not the week
                          entry("2026-11-01 23:30", "2026-11-02 00:15"),  # across Monday's midnight: 15 min in the week
                          entry("2026-11-02 00:30", "2026-11-02 01:00"),  # Monday
                          entry("2026-11-06 09:00", "2026-11-06 09:15"))  # today
        self.assertEqual(tot.today.seconds, 15 * 60)
        self.assertEqual(tot.week.seconds, (15 + 30 + 15) * 60)
        self.assertEqual(tot.month.seconds, (60 + 45 + 30 + 15) * 60)
        self.assertEqual(tot.month.brl, 1190.48)  # 2h30 at R$ 476,19 per hour (each piece rounded to cents)

    def test_month_start_when_the_week_began_in_the_last_month(self):
        tot = self.totals("2026-11-01 12:00",  # a Sunday: the week began on Monday 26 October
                          entry("2026-10-30 10:00", "2026-10-30 12:00"),  # the week, not the month
                          entry("2026-10-31 23:00", "2026-11-01 01:00"),  # across the month: 1 h in the month and today
                          entry("2026-11-01 10:00", "2026-11-01 10:30"))
        self.assertEqual(tot.today.seconds, 90 * 60)
        self.assertEqual(tot.week.seconds, (120 + 120 + 30) * 60)
        self.assertEqual(tot.month.seconds, 90 * 60)

    def test_the_band_counts_a_second_once(self):
        a, b = card("a", start="2026-11-06 08:00"), card("b", start="2026-11-06 09:00")  # one domain, both in Upstream
        e = entry("2026-11-06 08:30", "2026-11-06 10:00")
        now = t("2026-11-06 12:00")
        self.assertEqual(K.card_money(a, [e], self.rates, now).total.seconds, 90 * 60)
        self.assertEqual(K.card_money(b, [e], self.rates, now).total.seconds, 60 * 60)
        self.assertEqual(K.upstream_totals([a, b], [e], self.rates, now).today.seconds, 90 * 60)


class BoardTest(unittest.TestCase):
    def test_columns_in_stage_order_cards_in_arrival_order(self):
        cards = [card("a", start="2026-11-06 08:00"), card("b", start="2026-11-05 08:00"),
                 card("c", start="2026-11-04 08:00", moves=[("2026-11-05 10:00", "Downstream")]),
                 card("d", start="2026-11-01 08:00", moves=[("2026-11-02 08:00", "Feito")])]
        b = K.board(cards, [], {}, t("2026-11-06 12:00"))
        self.assertEqual([c.stage for c in b.columns], [K.Stage.TODO, K.Stage.UPSTREAM, K.Stage.DOWNSTREAM, K.Stage.DONE])
        self.assertEqual([[m.card.id for m in c.cards] for c in b.columns], [[], ["b", "a"], ["c"], ["d"]])

    def test_the_owners_order_comes_first_then_arrival(self):
        evs = [ev("card.created", x, f"2026-11-06 0{i}:00", title=x, domain="k", stage="Upstream")
               for i, x in enumerate("abcd", 1)]
        order = lambda es: [m.card.id for m in K.board(K.cards_from(es), [], {}, t("2026-11-06 12:00")).columns[1].cards]  # noqa: E731
        self.assertEqual(order(evs), ["a", "b", "c", "d"])
        evs.append(ev("card.prioritized", "c", "2026-11-06 09:00", position=0, stage="Upstream"))
        self.assertEqual(order(evs), ["c", "a", "b", "d"])
        evs.append(ev("card.prioritized", "d", "2026-11-06 09:01", position=0, stage="Upstream"))
        self.assertEqual(order(evs), ["d", "c", "a", "b"])
        evs.append(ev("card.prioritized", "a", "2026-11-06 09:02", position=1, stage="Upstream"))
        self.assertEqual(order(evs), ["d", "a", "c", "b"])  # the latest explicit order wins
        # rank N is N on screen, also past the ranked cards (here a and d are ranked, c and b after them)
        evs.append(ev("card.prioritized", "b", "2026-11-06 09:02", position=2, stage="Upstream"))
        self.assertEqual(order(evs), ["d", "a", "b", "c"])
        evs.append(ev("card.prioritized", "c", "2026-11-06 09:02", position=2, stage="Upstream"))
        self.assertEqual(order(evs), ["d", "a", "c", "b"])
        # moving out clears the rank there; coming back it is unranked again, by arrival
        evs.append(ev("card.moved", "d", "2026-11-06 09:03", stage="Todo", previous="Upstream"))
        evs.append(ev("card.moved", "d", "2026-11-06 09:04", stage="Upstream", previous="Todo"))
        self.assertEqual(order(evs), ["a", "c", "b", "d"])
        # a prioritize naming a stage the card left is ignored
        evs.append(ev("card.prioritized", "b", "2026-11-06 09:05", position=0, stage="Feito"))
        self.assertEqual(order(evs), ["a", "c", "b", "d"])

    def test_todo_is_the_first_stage_and_is_not_upstream_money(self):
        self.assertEqual(list(K.Stage)[0], K.Stage.TODO)
        c = card(start="2026-11-06 08:00", stage="Todo", moves=[("2026-11-06 10:00", "Upstream")])
        m = K.card_money(c, [entry("2026-11-06 08:00", "2026-11-06 11:00")], {"inv": RATE}, t("2026-11-06 12:00"))
        self.assertEqual(m.total.seconds, 3600)  # only 10:00-11:00: the Todo hours are waiting, not discovery

    def test_formats(self):
        self.assertEqual((K.brl(1234.5), K.brl(0), K.hm(3000), K.hm(3599), K.hm(7260)),
                         ("R$ 1.234,50", "R$ 0,00", "0h50", "0h59", "2h01"))
        self.assertEqual([K.stage_age(s) for s in (30, 307, 3 * 3600 + 300, 26 * 3600, 50 * 3600)],
                         ["há 30 s na etapa", "há 5 min 07 s na etapa", "há 3 h 05 min na etapa", "há 1 dia na etapa", "há 2 dias na etapa"])


class JournalTest(unittest.TestCase):
    """The journal: the one writer, its shape, what it refuses; the CLI; and the Costs journal read, never written."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["KANBAN_DIR"] = str(Path(self.tmp.name) / "kanban")
        os.environ["COSTS_DIR"] = str(Path(self.tmp.name) / "costs")
        os.environ["KANBAN_CONFIG"] = str(Path(self.tmp.name) / "config.json")  # absent: the default limits
        self.addCleanup(os.environ.pop, "KANBAN_CONFIG", None)

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = K.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_emit_shape(self):
        e = K.create("Kanban", "kanban")
        self.assertEqual(list(e), ["id", "event", "at", "actor", "card_id", "value"])
        self.assertEqual(e["value"], {"title": "Kanban", "domain": "kanban", "stage": "Todo"})
        m = K.move(e["card_id"], "downstream", actor="bili")
        self.assertEqual((m["event"], m["actor"], m["value"]), ("card.moved", "bili", {"stage": "Downstream", "previous": "Todo"}))
        self.assertEqual([json.loads(line)["id"] for line in K.journal_path().read_text().splitlines()], [e["id"], m["id"]])

    def test_emit_refuses_what_it_cannot_place(self):
        c = K.create("Kanban", "kanban")
        for bad in (lambda: K.create("", "kanban"), lambda: K.create("X", "not a slug"), lambda: K.create("X", "k", "Doing"),
                    lambda: K.move(c["card_id"], "Todo"), lambda: K.move("nope", "Feito"),
                    lambda: K.emit("card.deleted", {}, c["card_id"]), lambda: K.emit("card.moved", [1], c["card_id"])):
            with self.assertRaises(ValueError):
                bad()
        self.assertEqual(len(K.events()), 1)

    def test_find_by_id_prefix_or_title(self):
        a, b = K.create("Kanban", "kanban"), K.create("Paleta nativa", "dev-console")
        cards = K.cards_from(K.events())
        self.assertEqual(K.find(a["card_id"][:5], cards).id, a["card_id"])
        self.assertEqual(K.find("paleta NATIVA", cards).id, b["card_id"])
        K.create("Kanban", "tasks")
        with self.assertRaises(ValueError):
            K.find("kanban", K.cards_from(K.events()))  # two cards with that title

    def test_cli_and_the_costs_journal_is_only_read(self):
        costs = K._costs()
        now = datetime.now().astimezone()
        costs.emit("worth.updated", {"value_month": 20000, "goal_month": 50000, "paid_hours_day": 5, "work_days_month": 21})
        costs.emit("cost_center.updated", {"name": "Biliboss Skills", "kind": "investment", "domains": ["kanban"]},
                   "biliboss-skills")
        code, out, _ = self.cli("create", "Paleta nativa", "--domain", "dev-console")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["value"], {"title": "Paleta nativa", "domain": "dev-console", "stage": "Todo"})
        # a card that entered Upstream a minute ago (the API takes `at`; the CLI writes now)
        cid = K.create("Kanban", "kanban", "Upstream", at=now - timedelta(seconds=60))["card_id"]
        costs.emit("time_entry.started", {"domain": "kanban"}, "biliboss-skills", at=now - timedelta(seconds=90))
        costs.emit("time_entry.stopped", {"domain": "kanban", "seconds": 80, "rate_hour": RATE, "cost": 10.58},
                   "biliboss-skills", at=now - timedelta(seconds=10))
        before = (Path(os.environ["COSTS_DIR"]) / "events.jsonl").read_bytes()
        code, out, _ = self.cli("money", "--json")
        self.assertEqual(code, 0)
        band = json.loads(out)["totals"]
        self.assertEqual(band["today"]["seconds"], 50)  # 80 s from 90 s ago, clipped to the card's minute in Upstream
        self.assertEqual(band["today"]["brl"], round(50 * RATE / 3600, 2))  # the investment center: the goal's price
        code, out, _ = self.cli("money")
        self.assertIn(f"Hoje    {K.brl(round(50 * RATE / 3600, 2)):>14}  0h00", out)
        code, out, _ = self.cli("show", cid)
        self.assertIn(f"upstream  {K.brl(round(50 * RATE / 3600, 2))}  0h00", out)
        self.assertEqual(self.cli("move", "Kanban", "feito")[0], 0)
        code, _, err = self.cli("move", "Kanban", "Feito")
        self.assertEqual(code, 1)
        self.assertIn("already in Feito", err)
        code, out, _ = self.cli("list", "--stage", "feito")
        self.assertIn("Kanban", out)
        self.assertEqual((Path(os.environ["COSTS_DIR"]) / "events.jsonl").read_bytes(), before)

    def test_top_rank_rename_and_todo_from_the_cli(self):
        a = K.create("Alpha", "kanban", "Upstream")["card_id"]
        b = K.create("Beta", "kanban", "Upstream", force=True)["card_id"]
        self.assertEqual(self.cli("top", b)[0], 0)
        _, out, _ = self.cli("list", "--stage", "Upstream")
        self.assertLess(out.index("Beta"), out.index("Alpha"))
        code, out, _ = self.cli("rank", "Beta", "1")
        self.assertEqual(json.loads(out)["value"], {"position": 1, "stage": "Upstream"})
        code, out, _ = self.cli("top", a)  # a is now at the top, b right after
        self.assertEqual([m.card.id for m in K.read_board().columns[1].cards], [a, b])
        self.assertEqual(self.cli("rank", a, "-1")[0], 1)
        self.assertEqual(self.cli("rename", b, "Gamma")[0], 0)
        self.assertEqual(K.find("Gamma", K.cards_from(K.events())).id, b)
        code, _, err = self.cli("rename", b, "Gamma")
        self.assertEqual(code, 1)
        self.assertEqual(self.cli("rename", b, "  ")[0], 1)
        self.assertEqual(self.cli("move", b, "Todo")[0], 0)
        self.assertEqual([m.card.id for m in K.read_board().columns[0].cards], [b])
        self.assertEqual(json.loads(self.cli("create", "Waits", "--domain", "k", "--stage", "todo")[1])["value"]["stage"], "Todo")

    def test_create_defaults_to_todo(self):
        code, out, _ = self.cli("create", "Backlog", "--domain", "kanban")
        self.assertEqual((code, json.loads(out)["value"]["stage"]), (0, "Todo"))

    def test_upstream_is_full_at_one_card_and_refuses_with_exit_4(self):
        a = K.create("Via Blog", "kanban", "Upstream")["card_id"]
        b = K.create("Outro", "kanban")["card_id"]
        code, out, err = self.cli("move", b, "Upstream")
        self.assertEqual((code, out), (4, ""))
        self.assertIn("Upstream está cheio (1/1): Via Blog. Mova-o antes, ou use --force para registrar a exceção.", err)
        code, _, err = self.cli("create", "Terceiro", "--domain", "kanban", "--stage", "upstream")
        self.assertEqual(code, 4)
        self.assertIn("Via Blog", err)
        self.assertEqual(len(K.events()), 2)  # nothing was written
        # the card that is there already may be moved around; Downstream has no limit
        self.assertEqual(self.cli("move", b, "Downstream")[0], 0)
        self.assertEqual(self.cli("move", a, "Downstream")[0], 0)
        self.assertEqual(self.cli("move", b, "Upstream")[0], 0)  # the stage emptied: room again

    def test_force_goes_past_the_limit_and_is_recorded(self):
        K.create("Via Blog", "kanban", "Upstream")
        b = K.create("Outro", "kanban")["card_id"]
        code, out, _ = self.cli("move", b, "Upstream", "--force")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["value"], {"stage": "Upstream", "previous": "Todo", "forced": True})
        code, out, _ = self.cli("create", "Mais um", "--domain", "kanban", "--stage", "Upstream", "--force")
        self.assertEqual(json.loads(out)["value"]["forced"], True)
        self.assertNotIn("forced", K.create("Livre", "kanban")["value"])

    def test_limits_come_from_the_config_and_show_in_the_board_and_list(self):
        col = {c.stage.value: c for c in K.read_board().columns}
        self.assertEqual((col["Upstream"].limit, col["Downstream"].limit), (1, None))
        Path(os.environ["KANBAN_CONFIG"]).write_text(json.dumps({"stage_limits": {"Downstream": 2, "Upstream": 0}}))
        K.create("A", "kanban", "Upstream")
        K.create("B", "kanban", "Upstream")  # Upstream unlimited by the config
        K.create("C", "kanban", "Downstream")
        K.create("D", "kanban", "Downstream")
        self.assertEqual(self.cli("create", "E", "--domain", "kanban", "--stage", "Downstream")[0], 4)
        _, out, _ = self.cli("list")
        self.assertEqual(out.splitlines()[0], "Todo 0  Upstream 2  Downstream 2/2  Feito 0")
        Path(os.environ["KANBAN_CONFIG"]).unlink()
        _, out, _ = self.cli("list")
        self.assertEqual(out.splitlines()[0], "Todo 0  Upstream 2/1  Downstream 2  Feito 0")

    def test_projection_for_the_console(self):
        c = K.create("Kanban", "kanban")
        K.move(c["card_id"], "Downstream")
        j = K.KanbanJournal()
        [state] = j.read({})
        self.assertEqual((state["id"], state["stage"], state["domain"]), (c["card_id"], "Downstream", "kanban"))
        self.assertEqual(len(j.read({"id": c["card_id"], "history": True})), 2)
        self.assertEqual(len(j.read({"event": "card.moved"})), 1)
        self.assertEqual(j.read({"id": "_"}), {})


FAKE_GH = r'''#!/usr/bin/env python3
# fake gh: answers from $FAKE_GH_FILE ({"args joined by space": output | {"fail": true}}), logs every call; no GitHub.
import json, os, sys
key = " ".join(sys.argv[1:])
with open(os.environ["FAKE_GH_LOG"], "a") as f:
    f.write(key + "\n")
table = json.load(open(os.environ["FAKE_GH_FILE"]))
if key in table:
    ans = table[key]
elif sys.argv[1] in ("pr", "api") and ("close" in key or "-X DELETE" in key):
    ans = ""
else:
    print("fake gh: no answer for " + key, file=sys.stderr)
    sys.exit(1)
if isinstance(ans, dict) and ans.get("fail"):
    print("not found", file=sys.stderr)
    sys.exit(1)
print(ans if isinstance(ans, str) else json.dumps(ans))
'''

NOW = datetime.now(timezone.utc)  # the sweep reads the real clock; ages are relative to it (hours of margin)


def ago(hours: float) -> str:
    return (NOW - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


class GhCase(unittest.TestCase):
    """A fake gh on KANBAN_GH, a temp journal and config: the WIP check and the sweep never see GitHub."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        os.environ["KANBAN_DIR"] = str(self.home / "kanban")
        gh = self.home / "gh"
        gh.write_text(FAKE_GH, encoding="utf-8")
        gh.chmod(0o755)
        self.table: dict = {}
        self.log = self.home / "gh.log"
        self.answers = self.home / "answers.json"
        self.config = self.home / "config.json"
        for k, v in {"KANBAN_GH": str(gh), "FAKE_GH_LOG": str(self.log), "FAKE_GH_FILE": str(self.answers),
                     "KANBAN_CONFIG": str(self.config)}.items():
            os.environ[k] = v
            self.addCleanup(os.environ.pop, k, None)
        self.answers.write_text("{}", encoding="utf-8")

    def gh(self, **answers):
        self.table.update({k.replace("__", " "): v for k, v in answers.items()})

    def put(self, args: str, answer):
        self.table[args] = answer
        self.answers.write_text(json.dumps(self.table), encoding="utf-8")

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = K.main(list(args))
        return code, out.getvalue(), err.getvalue()


def prs(n: int, repo="o/r") -> list[dict]:
    return [{"number": i, "title": f"PR {i}", "headRefName": f"b{i}", "createdAt": ago(1), "url": f"https://x/{i}"}
            for i in range(1, n + 1)]


LIST = "pr list -R {} --state open --limit 200 --json number,title,headRefName,createdAt,url"


class WipTest(GhCase):
    def test_under_at_and_over_the_limit(self):
        for n, code in ((2, 0), (3, 3), (4, 3)):
            self.put(LIST.format("o/r"), prs(n))
            got, out, _ = self.cli("wip", "--repo", "o/r")
            self.assertEqual(got, code, n)
            self.assertIn(f"{n} open PR(s), limit 3", out)

    def test_limit_comes_from_the_config_default_three(self):
        self.assertEqual(K.wip_limit("o/r"), 3)
        self.config.write_text(json.dumps({"wip": {"limit": 5, "repos": {"o/small": 1}}}), encoding="utf-8")
        self.assertEqual((K.wip_limit("o/r"), K.wip_limit("o/small")), (5, 1))
        self.put(LIST.format("o/r"), prs(4))
        self.assertEqual(self.cli("wip", "--repo", "o/r", "--json")[0], 0)
        self.put(LIST.format("o/small"), prs(1))
        self.assertEqual(self.cli("wip", "--repo", "o/small")[0], 3)

    def test_repo_defaults_to_the_current_directory_and_a_gh_failure_is_an_error(self):
        self.put("repo view --json nameWithOwner", {"nameWithOwner": "o/here"})
        self.put(LIST.format("o/here"), prs(0))
        code, out, _ = self.cli("wip")
        self.assertEqual((code, "o/here" in out), (0, True))
        code, _, err = self.cli("wip", "--repo", "o/unknown")
        self.assertEqual(code, 1)  # not 3: an unknown count is not "over the limit"
        self.assertIn("kanban:", err)


def branch_answers(t: GhCase, repo: str, branches: dict[str, dict], default="main"):
    """branches: name -> {age_h, ahead, files: {path: (branch sha, main sha)}}."""
    t.put(f"api repos/{repo}", {"default_branch": default})
    t.put(f"api repos/{repo}/branches?per_page=100", [{"name": default}] + [{"name": n} for n in branches])
    for n, b in branches.items():
        t.put(f"api repos/{repo}/commits/{n}", {"commit": {"committer": {"date": ago(b["age_h"])}}})
        t.put(f"api repos/{repo}/compare/{default}...{n}",
              {"ahead_by": b.get("ahead", 0), "files": [{"filename": p} for p in b.get("files", {})]})
        for p, (on_branch, on_main) in b.get("files", {}).items():
            t.put(f"api repos/{repo}/contents/{p}?ref={n}", {"sha": on_branch} if on_branch else {"fail": True})
            t.put(f"api repos/{repo}/contents/{p}?ref={default}", {"sha": on_main} if on_main else {"fail": True})


class SweepTest(GhCase):
    def setUp(self):
        super().setUp()
        old = {"number": 7, "title": "old", "headRefName": "landed", "createdAt": ago(60), "url": "u7"}
        wip = {"number": 8, "title": "work", "headRefName": "wip", "createdAt": ago(100), "url": "u8"}
        fresh = {"number": 9, "title": "fresh", "headRefName": "fresh", "createdAt": ago(5), "url": "u9"}
        self.put(LIST.format("o/r"), [old, wip, fresh])
        branch_answers(self, "o/r", {
            "landed": {"age_h": 60, "ahead": 2, "files": {"a.py": ("s1", "s1"), "gone.py": (None, None)}},  # squash-merged
            "wip": {"age_h": 100, "ahead": 1, "files": {"b.py": ("s2", "s3")}},
            "fresh": {"age_h": 5},
            "merged-old": {"age_h": 90, "ahead": 0},
            "orphan": {"age_h": 80, "ahead": 3, "files": {"c.py": ("s4", "s5")}},
        })

    def run_sweep(self, *args):
        return self.cli("sweep", "--repos", "o/r", "--json", *args)

    def test_dry_run_lists_and_changes_nothing(self):
        code, out, _ = self.run_sweep()
        self.assertEqual(code, 0)
        by = {i["ref"]: i["action"] for i in json.loads(out)["items"]}
        self.assertEqual(by, {"#7 landed": "close", "#8 wip": "aged", "merged-old": "delete", "orphan": "decision"})
        self.assertEqual(K.events(), [])
        self.assertFalse([c for c in self.calls() if "close" in c or "DELETE" in c])  # no write at all

    def test_apply_closes_deletes_and_records_the_rest_once(self):
        code, out, _ = self.run_sweep("--apply")
        self.assertEqual(code, 0)
        calls = self.calls()
        self.assertIn("pr close 7 -R o/r --comment Closed by the kanban sweep: this content is already in main.", calls)
        self.assertIn("api -X DELETE repos/o/r/git/refs/heads/merged-old", calls)
        # never touched: the unmerged branch and PR, the fresh PR, main
        self.assertEqual([c for c in calls if "wip" in c and ("close" in c or "DELETE" in c)], [])
        self.assertEqual([c for c in calls if "orphan" in c and "DELETE" in c], [])
        self.assertEqual([c for c in calls if "merge" in c.split()[:2]], [])
        evs = [(e["event"], e["value"]["ref"]) for e in K.events()]
        self.assertEqual(sorted(evs), [("decision.requested", "orphan"), ("item.aged", "#8 wip"), ("item.aged", "orphan")])
        aged = next(e for e in K.events() if e["event"] == "item.aged" and e["value"]["ref"] == "#8 wip")
        self.assertEqual({k: v for k, v in aged["value"].items() if k != "age_h"}, {"repo": "o/r", "kind": "pr", "ref": "#8 wip"})
        self.assertAlmostEqual(aged["value"]["age_h"], 100, delta=0.5)
        self.assertIsNone(aged["card_id"])
        before = len(K.events())
        self.run_sweep("--apply")  # the daily sweep says each thing once
        self.assertEqual(len(K.events()), before)

    def test_a_deploying_repo_only_ever_gets_decision_requested(self):
        self.put(LIST.format("viacorretor/the-viacorretor"),
                 [{"number": 3, "title": "x", "headRefName": "landed2", "createdAt": ago(70), "url": "u"}])
        branch_answers(self, "viacorretor/the-viacorretor", {"landed2": {"age_h": 70, "ahead": 0}, "stale": {"age_h": 99, "ahead": 0}})
        code, out, _ = self.cli("sweep", "--repos", "viacorretor/the-viacorretor", "--apply", "--json")
        self.assertEqual(code, 0)
        self.assertEqual({i["action"] for i in json.loads(out)["items"]}, {"decision"})  # even in main: not closed, not deleted
        self.assertFalse([c for c in self.calls() if "close" in c or "DELETE" in c])
        self.assertEqual({e["event"] for e in K.events()}, {"item.aged", "decision.requested"})
        self.assertEqual({e["value"]["repo"] for e in K.events()}, {"viacorretor/the-viacorretor"})

    def test_hours_and_text_output_and_errors(self):
        code, out, _ = self.cli("sweep", "--repos", "o/r", "--hours", "95")
        self.assertEqual(code, 0)
        self.assertIn("sweep >95 h (dry run): 1 item(s): 1 aged", out)
        code, _, err = self.cli("sweep", "--repos", "o/missing")
        self.assertEqual(code, 1)
        self.assertIn("o/missing", err)

    def test_new_events_are_validated(self):
        with self.assertRaises(ValueError):
            K.emit("item.aged", {"repo": "o/r", "kind": "tag", "ref": "x", "age_h": 1})
        with self.assertRaises(ValueError):
            K.emit("decision.requested", {"repo": "o/r", "ref": "x"})
        self.assertIn("item.aged", K.KNOWN_EVENTS)
        self.assertIn("decision.requested", K.KNOWN_EVENTS)
        K.create("A card", "kanban")
        self.assertEqual(len(K.read_board().columns[0].cards), 1)  # cardless events never become cards


STUB_HERMES_SH = '''#!/usr/bin/env bash
echo "$*" >> "$STUB_DIR/hermes.log"
printf '{"slug":"%s","session_id":"local-x","session":"created","tmux":"created"}\\n' "$2"
'''
STUB_TMUX = '''#!/usr/bin/env bash
echo "$*" >> "$STUB_DIR/tmux.log"
[ "$1" = "list-clients" ] && printf '100 /dev/ttys001\\n200 /dev/ttys009\\n'
exit 0
'''


class PullTest(JournalTest):
    """pull: the card (reused or created in Upstream), the cost center binding, the workspace and the client; the
    hermes.sh and tmux it calls are stubs, so no real session is made and no real client is switched."""

    def setUp(self):
        super().setUp()
        d = Path(self.tmp.name)
        for name, body in (("hermes.sh", STUB_HERMES_SH), ("tmux", STUB_TMUX)):
            (d / name).write_text(body)
            (d / name).chmod(0o755)
        for k, v in (("HERMES_SH", d / "hermes.sh"), ("TMUX_BIN", d / "tmux"), ("STUB_DIR", d)):
            os.environ[k] = str(v)
            self.addCleanup(os.environ.pop, k, None)
        self.d = d
        K._costs.cache_clear()
        self.addCleanup(K._costs.cache_clear)

    def pull(self, *args):
        code, out, err = self.cli("pull", "Sygnal 0.2", "--repo", self.tmp.name, "--json", *args)
        return code, (json.loads(out.strip().splitlines()[-1]) if out.strip() else None), err

    def test_slug_is_the_same_as_tmux_focus(self):
        self.assertEqual(K.slug("Sygnal 0.2"), "sygnal-0-2")
        self.assertEqual(K.slug("Ação rápida!"), "acao-rapida")

    def test_creates_in_upstream_then_is_idempotent(self):
        code, r, _ = self.pull("--domain", "sygnal", "--no-switch")
        self.assertEqual(code, 0)
        self.assertEqual((r["slug"], r["card"]["state"], r["card"]["stage"], r["switched"]), ("sygnal-0-2", "created", "Upstream", None))
        self.assertEqual(r["workspace"]["session_id"], "local-x")
        code, again, _ = self.pull("--domain", "sygnal", "--no-switch")
        self.assertEqual((code, again["card"]["state"], again["card"]["id"]), (0, "reused", r["card"]["id"]))
        self.assertEqual(len(K.cards_from(K.events())), 1)
        self.assertEqual([json.loads(x)["event"] for x in K.journal_path().read_text().splitlines()], ["card.created"])
        self.assertIn("workspace sygnal-0-2 --repo", (self.d / "hermes.log").read_text())

    def test_a_todo_card_is_pulled_to_upstream(self):
        c = K.create("Sygnal 0.2", "sygnal")
        code, r, _ = self.pull()
        self.assertEqual((code, r["card"]["id"], r["card"]["state"]), (0, c["card_id"], "moved from Todo"))
        self.assertEqual(str(K.cards_from(K.events())[0].stage), "Upstream")

    def test_full_upstream_exits_5_and_swap_sends_the_current_back(self):
        cur = K.create("Via Blog", "via-blog", "Upstream")
        code, out, err = self.cli("pull", "Sygnal 0.2", "--repo", self.tmp.name, "--no-switch")
        self.assertEqual((code, json.loads(out)), (5, {"full": "Via Blog"}))
        self.assertEqual(len(K.events()), 1)  # nothing written, no session made
        self.assertFalse((self.d / "hermes.log").exists())
        code, r, _ = self.pull("--domain", "sygnal", "--no-switch", "--swap")
        self.assertEqual(code, 0)
        stages = {c.title: str(c.stage) for c in K.cards_from(K.events())}
        self.assertEqual(stages, {"Via Blog": "Todo", "Sygnal 0.2": "Upstream"})
        self.assertEqual(K.cards_from(K.events())[0].id, cur["card_id"])

    def test_center_binds_the_domain_once(self):
        import costs  # noqa: PLC0415 - cost-track's, found through the sibling skill
        costs.emit("cost_center.updated", {"name": "Mukutu", "kind": "client", "pays_month": 8000}, "mukutu")
        costs.emit("cost_center.updated", {"name": "Skills", "kind": "investment", "domains": ["sygnal", "kanban"]}, "skills")
        code, r, _ = self.pull("--domain", "sygnal", "--no-switch", "--center", "mukutu")
        self.assertEqual((code, r["center"]), (0, {"id": "mukutu", "domain": "sygnal", "bound_now": True}))
        self.assertEqual(costs.center_of("sygnal"), "mukutu")
        self.assertEqual(costs.centers()["mukutu"]["pays_month"], 8000)  # the center's last value, kept
        self.assertEqual(costs.centers()["skills"]["domains"], ["kanban"])  # a domain has one center
        n = len(costs.events())
        code, r, _ = self.pull("--domain", "sygnal", "--no-switch", "--center", "mukutu")
        self.assertEqual((r["center"]["bound_now"], len(costs.events())), (False, n))
        code, _, err = self.pull("--no-switch", "--center", "nope")
        self.assertEqual(code, 1)
        self.assertIn("mukutu", err)

    def test_switches_the_most_recent_client_unless_told_not_to(self):
        code, r, _ = self.pull("--domain", "sygnal")
        self.assertEqual((code, r["switched"]), (0, "/dev/ttys009"))
        self.assertIn("switch-client -c /dev/ttys009 -t =sygnal-0-2", (self.d / "tmux.log").read_text())
        (self.d / "tmux.log").unlink()
        self.pull("--no-switch")
        self.assertFalse((self.d / "tmux.log").exists())


if __name__ == "__main__":
    unittest.main()
