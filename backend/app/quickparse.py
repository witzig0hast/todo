"""Schnelleingabe ohne KI: „morgen 15 Uhr Zahnarzt #privat !!“ -> Titel, Fälligkeit, Priorität, Tags, Liste, Wiederholung.

Bewusst regelbasiert (deutsch), damit es sofort, offline vom Modell und vorhersagbar funktioniert. Erkannte Teile
werden aus dem Titel entfernt; was nicht eindeutig ist, bleibt einfach Text."""
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .recurrence import FMT, Recurrence, describe

WEEKDAYS = {"montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3, "freitag": 4, "samstag": 5, "sonnabend": 5, "sonntag": 6}
MONTHS = {"januar": 1, "jan": 1, "februar": 2, "feb": 2, "märz": 3, "maerz": 3, "mär": 3, "april": 4, "apr": 4, "mai": 5,
          "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
          "oktober": 10, "okt": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12}
NUMBERS = {"ein": 1, "eine": 1, "einen": 1, "einem": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
           "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12, "zwoelf": 12}
DAYPARTS = {"früh": 8, "frueh": 8, "morgens": 8, "morgen": 8, "vormittag": 10, "vormittags": 10, "mittag": 12, "mittags": 12,
            "nachmittag": 15, "nachmittags": 15, "abend": 19, "abends": 19, "nacht": 22, "nachts": 22}
PM_PARTS = {"nachmittag", "nachmittags", "abend", "abends", "nacht", "nachts"}

_alt = lambda words: "|".join(sorted(map(re.escape, words), key=len, reverse=True))  # noqa: E731
WD, MON, NUM, PART = _alt(WEEKDAYS), _alt(MONTHS), _alt(NUMBERS), _alt(DAYPARTS)
PRE = r"(?:\b(?:bis|am|ab|für|fuer|zum|spätestens|spaetestens)\s+)?"
DAYPART_ONLY = _alt(k for k in DAYPARTS if k != "morgen")  # „morgen“ allein heißt „morgen“ (Tag), nicht „morgens“


def _num(s: str) -> int:
    return int(s) if s.isdigit() else NUMBERS[s.lower()]


class _Parse:
    def __init__(self, text: str, now: datetime, lists: dict[int, str]):
        self.s = f" {text} "
        self.now = now  # lokale, zeitzonenbehaftete Zeit
        self.lists = lists
        self.day: date | None = None
        self.hm: tuple[int, int] | None = None
        self.part: str | None = None
        self.exact: datetime | None = None
        self.weekday: int | None = None
        self.monthday: int | None = None
        self.rec: dict | None = None
        self.priority = 0
        self.tags: list[str] = []
        self.list_id: int | None = None

    # Teilstring entfernen, wenn handler ihn akzeptiert (True); first=True: nur der erste Treffer
    def take(self, pattern: str, handler, first: bool = True) -> None:
        for m in list(re.finditer(pattern, self.s, re.IGNORECASE)):
            if handler(m) is not False:
                self.s = self.s[:m.start()] + " " * (m.end() - m.start()) + self.s[m.end():]
                if first:
                    return

    # ---------------------------------------------------------------- Teile
    def tag(self, m):
        t = m.group(1).lower()
        if len(self.tags) >= 10:
            return False
        if t not in self.tags:
            self.tags.append(t)

    def list_ref(self, m):
        if self.list_id is not None:
            return False
        key = re.sub(r"[\s_\-]", "", m.group(1).lower())
        norm = {i: re.sub(r"[\s_\-]", "", n.lower()) for i, n in self.lists.items()}
        exact = [i for i, n in norm.items() if n == key]
        prefix = [i for i, n in norm.items() if n.startswith(key)]
        hit = exact[0] if exact else (prefix[0] if len(prefix) == 1 else None)
        if hit is None:
            return False
        self.list_id = hit

    def prio(self, m):
        v = m.group(1).lower().strip("!")
        p = {"hoch": 3, "mittel": 2, "niedrig": 1}.get(v) or (int(v) if v.isdigit() else len(m.group(1)))
        self.priority = max(self.priority, min(3, p))

    def rec_simple(self, m):
        w = re.sub(r"\s+", " ", m.group(1).lower())
        freq = {"täglich": "daily", "taeglich": "daily", "jeden tag": "daily", "werktags": "weekdays", "jeden werktag": "weekdays",
                "wöchentlich": "weekly", "woechentlich": "weekly", "jede woche": "weekly", "monatlich": "monthly",
                "jeden monat": "monthly", "jährlich": "yearly", "jaehrlich": "yearly", "jedes jahr": "yearly"}.get(w)
        if w in ("zweiwöchentlich", "zweiwoechentlich"):
            self.rec = {"freq": "weekly", "interval": 2}
        elif freq:
            self.rec = {"freq": freq, "interval": 1}

    def rec_every_n(self, m):
        n = _num(m.group(1))
        if not 1 <= n <= 365:
            return False
        unit = m.group(2).lower()
        self.rec = {"freq": {"tag": "daily", "woc": "weekly", "mon": "monthly", "jah": "yearly"}[unit[:3]], "interval": n}

    def rec_weekday(self, m):
        self.weekday = WEEKDAYS[(m.group(1) or m.group(2)).lower()]
        self.rec = {"freq": "weekly", "interval": 1}

    def rec_monthday(self, m):
        d = int(m.group(1))
        if not 1 <= d <= 31:
            return False
        self.monthday = d
        self.rec = {"freq": "monthly", "interval": 1}

    def after_done(self, _m):
        if self.rec is None:
            return False
        self.rec["after_done"] = True

    def relative(self, m):
        amount = m.group(1).lower()
        unit = m.group(2).lower()
        if amount in ("einer halben", "einem halben"):
            minutes = 30
        elif amount == "einer viertel":
            minutes = 15
        else:
            n = _num(amount)
            if unit.startswith(("min",)):
                minutes = n
            elif unit.startswith(("stu", "std")) or unit == "h":
                minutes = n * 60
            elif unit.startswith("tag"):
                self.day = self.now.date() + timedelta(days=n)
                return
            elif unit.startswith("woc"):
                self.day = self.now.date() + timedelta(weeks=n)
                return
            elif unit.startswith("mon"):
                self.day = _add_months(self.now.date(), n)
                return
            else:
                self.day = _add_months(self.now.date(), 12 * n)
                return
            if minutes > 60 * 24 * 60:
                return False
        self.exact = (self.now + timedelta(minutes=minutes)).replace(second=0, microsecond=0)

    def date_num(self, m):
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        return self._set_date(d, mo, int(y) if y else None)

    def date_name(self, m):
        return self._set_date(int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3)) if m.group(3) else None)

    def _set_date(self, d: int, mo: int, y: int | None):
        if self.day is not None:
            return False
        year = (2000 + y if y < 100 else y) if y else self.now.year
        try:
            value = date(year, mo, d)
        except ValueError:
            return False
        if y is None and value < self.now.date():
            try:
                value = date(year + 1, mo, d)
            except ValueError:  # 29.02.
                return False
        self.day = value

    def day_word(self, m):
        if self.day is not None:
            return False
        w = m.group(1).lower()
        self.day = self.now.date() + timedelta(days={"heute": 0, "morgen": 1}.get(w, 2))
        if m.group(2):
            self.part = m.group(2).lower()

    def weekday_word(self, m):
        if self.day is not None:
            return False
        target = WEEKDAYS[m.group(1).lower()]
        delta = (target - self.now.weekday()) % 7 or 7
        self.day = self.now.date() + timedelta(days=delta)
        if m.group(2):
            self.part = m.group(2).lower()

    def special(self, m):
        if self.day is not None:
            return False
        w = re.sub(r"\s+", " ", m.group(0).strip().lower())
        today = self.now.date()
        if "übernächste woche" in w or "uebernaechste woche" in w:
            self.day = today + timedelta(days=7 - today.weekday() + 7)
        elif "woche" in w and ("nächste" in w or "naechste" in w or "kommende" in w):
            self.day = today + timedelta(days=7 - today.weekday())
        elif "ende der woche" in w:
            self.day = today + timedelta(days=(4 - today.weekday()) % 7)
        elif "wochenende" in w:
            self.day = today if today.weekday() >= 5 else today + timedelta(days=5 - today.weekday())
        elif "monat" in w and ("nächste" in w or "naechste" in w or "kommende" in w):
            self.day = _add_months(today.replace(day=1), 1)
        else:  # Monatsende
            self.day = _add_months(today.replace(day=1), 1) - timedelta(days=1)

    def time_hm(self, m):
        if self.hm is not None or self.exact is not None:
            return False
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if h > 23 or mi > 59:
            return False
        self.hm = (h, mi)
        if m.lastindex and m.lastindex >= 3 and m.group(3):
            self.part = m.group(3).lower()

    def daypart(self, m):
        if self.part is not None or (self.day is None and self.hm is None and self.weekday is None):
            return False
        self.part = m.group(1).lower()

    # ---------------------------------------------------------------- Ablauf
    def run(self) -> dict:
        t = self.take
        t(r"(?<!\S)#([\w\-]{1,30})(?!\S)", self.tag, first=False)
        if self.lists:
            t(r"(?<!\S)@([\w\-äöüß]{1,40})(?!\S)", self.list_ref)
        t(r"(?<!\S)(!{1,3}|!(?:hoch|mittel|niedrig)|![123])(?!\S)", self.prio)
        t(r"(?<=\w)(!{2,3})(?!\S)", self.prio)
        t(r"\b(täglich|taeglich|jeden\s+tag|werktags|jeden\s+werktag|wöchentlich|woechentlich|zweiwöchentlich|zweiwoechentlich"
          r"|jede\s+woche|monatlich|jeden\s+monat|jährlich|jaehrlich|jedes\s+jahr)\b", self.rec_simple)
        t(rf"\balle\s+(\d{{1,3}}|{NUM})\s+(tage|wochen|monate|jahre)\b", self.rec_every_n)
        t(rf"\b(?:jeden|jede|immer)\s+({WD})\b|\b({WD})s\b", self.rec_weekday)
        t(r"\bjeden\s+(\d{1,2})\.(?!\d)(?:\s+des\s+monats\b)?", self.rec_monthday)
        t(r"\b(?:ab|nach)\s+erledigung\b", self.after_done)
        t(rf"{PRE}\bin\s+(\d{{1,4}}|einer\s+halben|einem\s+halben|einer\s+viertel|{NUM})\s*"
          r"(minuten|minute|min|stunden|stunde|std|h|tagen|tag|wochen|woche|monaten|monat|jahren|jahr)\b", self.relative)
        t(rf"{PRE}\b(\d{{1,2}})\.(\d{{1,2}})\.(\d{{4}}|\d{{2}})?(?!\d)", self.date_num)
        t(rf"{PRE}\b(\d{{1,2}})\.?\s*({MON})\b\.?(?:\s+(\d{{4}}))?", self.date_name)
        t(rf"{PRE}\b(heute|morgen|übermorgen|uebermorgen)\b(?:\s+({PART})\b)?", self.day_word)
        t(rf"{PRE}\b(?:(?:nächsten|nächste|naechsten|naechste|kommenden|diesen|diesem)\s+)?({WD})(?:\s*({DAYPART_ONLY}))?\b",
          self.weekday_word)
        t(rf"{PRE}\b(?:übernächste\s+woche|uebernaechste\s+woche|(?:nächste|naechste|kommende)\s+woche|ende\s+der\s+woche"
          r"|(?:am\s+)?wochenende|(?:nächsten|naechsten|kommenden)\s+monat|ende\s+des\s+monats|monatsende)\b", self.special)
        t(rf"(?:\bum\s+)?(?<![\d.:])\b([01]?\d|2[0-3]):([0-5]\d)\b(?:\s*uhr\b)?(?:\s+({DAYPART_ONLY})\b)?", self.time_hm)
        t(rf"\bum\s+([01]?\d|2[0-3])\.([0-5]\d)\b(?:\s*uhr\b)?(?:\s+({DAYPART_ONLY})\b)?", self.time_hm)
        t(rf"(?<![\d.:])\b([01]?\d|2[0-3])\.([0-5]\d)\s*uhr\b(?:\s+({DAYPART_ONLY})\b)?", self.time_hm)
        t(rf"(?:\bum\s+)?(?<![\d.:])\b([01]?\d|2[0-3])\s*uhr\b(?:\s+([0-5]?\d)\b(?!\s*(?:min|minuten)\b))?(?:\s+({DAYPART_ONLY})\b)?",
          self.time_hm)
        t(rf"\bum\s+([01]?\d|2[0-3])\b(?![.:,]?\d)()(?:\s+({DAYPART_ONLY})\b)?", self.time_hm)
        t(rf"\b({DAYPART_ONLY})\b", self.daypart)
        return self.result()

    def due(self) -> datetime | None:
        if self.exact is not None:
            return self.exact
        tz = self.now.tzinfo
        hm = self.hm
        if hm is not None and self.part in PM_PARTS and hm[0] < 12 and not (self.part.startswith("nacht") and hm[0] < 5):
            hm = (hm[0] + 12, hm[1])
        if hm is None and self.part:
            hm = (DAYPARTS[self.part], 0)
        clock = time(*(hm or (9, 0)))
        day = self.day
        if hm is None and day == self.now.date() and datetime.combine(day, clock, tz) <= self.now:
            # „heute“ ohne Uhrzeit, 9 Uhr schon vorbei: nächste volle Stunde statt sofort überfällig
            clock = time(self.now.hour + 1, 0) if self.now.hour < 23 else time(23, 59)
        if day is None and self.weekday is not None:
            delta = (self.weekday - self.now.weekday()) % 7
            if delta == 0 and datetime.combine(self.now.date(), clock, tz) <= self.now:
                delta = 7
            day = self.now.date() + timedelta(days=delta)
        if day is None and self.monthday is not None:
            day = _next_monthday(self.now, self.monthday, clock)
        if day is None and (hm is not None or self.rec):
            day = self.now.date()
            if datetime.combine(day, clock, tz) <= self.now:
                day += timedelta(days=1)
        if day is None:
            return None
        return datetime.combine(day, clock, tz)

    def result(self) -> dict:
        due = self.due()
        title = re.sub(r"\s+", " ", self.s).strip()
        # übrig gebliebene Füllwörter/Satzzeichen an den Rändern entfernen
        for _ in range(3):
            title = re.sub(r"^(?:am|um|bis|ab|für|fuer|zum|und|,|-|–|:)\s+|\s+(?:am|um|bis|ab|für|fuer|zum|und|,|-|–)$|^[,\-–:]+|[,\-–:]+$",
                           "", title, flags=re.IGNORECASE).strip()
        rec = None
        if self.rec:
            rec = Recurrence(**self.rec).model_dump()
        return {"title": title, "due_at": due.astimezone(ZoneInfo("UTC")).strftime(FMT) if due else None,
                "priority": self.priority, "tags": self.tags, "list_id": self.list_id, "recurrence": rec,
                "recurrence_text": describe(Recurrence(**rec)) if rec else None}


def _add_months(d: date, months: int) -> date:
    import calendar

    m = d.month - 1 + months
    y, mo = d.year + m // 12, m % 12 + 1
    return d.replace(year=y, month=mo, day=min(d.day, calendar.monthrange(y, mo)[1]))


def _next_monthday(now: datetime, day: int, clock: time) -> date:
    import calendar

    d = now.date().replace(day=1)
    for _ in range(14):
        last = calendar.monthrange(d.year, d.month)[1]
        cand = d.replace(day=min(day, last))
        if datetime.combine(cand, clock, now.tzinfo) > now:
            return cand
        d = _add_months(d, 1)
    return now.date()


def parse(text: str, now: datetime, lists: dict[int, str] | None = None) -> dict:
    """text: Eingabe; now: lokale Zeit des Benutzers (mit tzinfo); lists: zugängliche Listen {id: name}."""
    out = _Parse(text.strip(), now, lists or {}).run()
    if not out["title"]:  # nur Datum o. ä. eingegeben: lieber den ganzen Text als Titel behalten
        out["title"] = re.sub(r"\s+", " ", text).strip()
    return out
