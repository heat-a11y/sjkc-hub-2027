"""Photograph engine for the exam papers.

Pure-stdlib: each reading part's topic is mapped to a Wikimedia Commons search
query, downloaded thumbnails are cached under the app data dir, and embedded as
JPEGs in the .docX (rendered identically in LibreOffice/Word).  The HTML preview
inlines the same JPEGs.  When no photo is available (e.g. fully offline and
uncached) the part simply renders without a picture.

Photo subjects are chosen from the passage text by ``query_for_text`` so every
reading article gets a picture that is actually related to its questions.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import time
import urllib.parse
import urllib.request

EMU_CM = 360000

# Photographs are drawn from Wikimedia Commons (keyless JSON search API).  Every
# image there is freely licensed (CC / public domain), so papers using them can
# be redistributed.  Downloaded thumbnails are cached under the app data dir, so
# regeneration is fully offline after the first run.
_PHOTO_SOURCE = "https://commons.wikimedia.org/w/api.php"
_PHOTO_UA = "exam-gen/1.0 (offline exam-paper generator built with urllib)"
_PHOTO_TIMEOUT = 10
_PHOTO_MAX_BYTES = 512 * 1024
# Total wall-clock budget spent on photo searches per process.  Prevents an
# offline or blackholed network from stalling paper generation.  It is
# treated as a shared batch *deadline* (a query may fetch as long as the wall
# clock is inside the window), not a counter each worker thread races to
# drain, so paper topics fetched in parallel all resolve instead of the first
# query to finish eating the whole budget (Round 15 fix).
_PHOTO_BUDGET_SECS = 16.0

# Set EXAM_GEN_OFFLINE=1 to never hit the network (thumbnail cache reads still
# work); generation then proceeds without pictures.
_OFFLINE = os.environ.get("EXAM_GEN_OFFLINE") == "1"

_budget_left = _PHOTO_BUDGET_SECS
_failed_queries: set[str] = set()

if not _OFFLINE:
    socket.setdefaulttimeout(_PHOTO_TIMEOUT)


def _photo_cache_dir() -> str:
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "exam-gen", "photos")


# ---------------------------------------------------------------------------
# classifier
# ---------------------------------------------------------------------------

ART_KEYWORDS = {
    "school": ["school", "classroom", "teacher", "pupils", "student", "library",
               "assembly", "homework", "learns", "lesson", "recess",
               "gotong-royong", "clean-up", "books", "pencil", "rubber",
               "eraser", "scissors", "crayon", "notebook", "ruler", "bell"],
    "market": ["market", "stall", "seller", "buy", "sells", "fish", "rambutan",
               "durian", "fruit", "vegetables", "hawker", "coconut", "mango",
               "banana", "pineapple", "seafood"],
    "animals": ["tiger", "lion", "monkey", "elephant", "animal", "zoo", "bird",
                "hornbill", "tapir", "pangolin", "proboscis", "ranger", "forest",
                "jungle", "cats", "dog", "giraffe", "kangaroo", "crocodile",
                "panda", "parrot", "rabbit", "hamster", "turtle", "duck",
                "lizard", "spider", "frog", "ant", "bee", "butterfly", "snake",
                "owl", "bear", "wolf", "fox", "zebra", "hippo", "octopus",
                "dolphin", "seal", "whale", "swan", "tortoise", "mouse", "rat",
                "cock", "crow", "hare", "deer", "hen", "cow", "chick",
                "rooster", "duckling", "jellyfish", "seahorse", "starfish",
                "crab", "shark", "goat", "sheep", "horse"],
    "river": ["river", "riverbank", "water", "fish swimming", "tadpole",
              "sungai", "stream"],
    "farm": ["farm", "farmer", "hens", "chickens", "goats", "sheep", "padi",
             "kampung", "garden", "hen", "chick", "rooster", "cow", "horse",
             "donkey", "rice"],
    "food": ["food", "rice", "nasi lemak", "satay", "roti", "kuih", "lasagna",
             "cook", "cooking", "meal", "soup", "curry", "wok", "noodles",
             "eats", "breakfast", "pancake", "sandwich", "salad", "ice cream",
             "fried chicken", "milk", "bread", "egg", "jam", "juice", "cake",
             "cup", "plate", "bowl", "spoon", "fork", "toast", "cereal",
             "sausage", "corn", "cookies", "feast", "porridge", "omelette",
             "pastry", "sambal", "laksa", "cheese", "pie"],
    "festival": ["new year", "festival", "lantern", "mooncake", "lion dance",
                 "red packet", "dragon", "random", "decorations", "celebration",
                 "deepavali", "hari raya", "christmas", "diwali", "eid",
                 "parade", "greeting"],
    "town": ["city", "town", "kuala lumpur", "twin towers", "tower", "penang",
             "batu caves", "skyscraper", "landmark", "tourist", "mosque",
             "temple", "shop"],
    "transport": ["bus", "train", "lrt", "ferry", "bicycle", "car", "lorry",
                  "transport", "travel", "funicular", "monorail", "airplane",
                  "aeroplane", "helicopter", "ship", "ticket", "boat"],
    "people": ["doctor", "nurse", "firefighter", "teacher", "pilot", "job",
               "work", "occupation", "headmaster", "engineer", "chef",
               "dentist", "police", "veterinarian"],
    "rain": ["rain", "monsoon", "flood", "cloud", "storm", "umbrella",
             "raincoat", "boots", "thunder", "lightning", "sun", "wind",
             "rainbow", "puddle", "frost"],
    "sea": ["sea", "beach", "island", "boat", "fisherman", "coral", "ocean",
            "seashell", "sandcastle", "lighthouse", "crab", "shark", "whale",
            "starfish", "octopus", "dolphin", "turtle", "seal", "jellyfish",
            "seahorse", "sand", "wave", "shell"],
    "recycle": ["recycle", "recycling", "rubbish", "bin", "bottles", "waste",
                "environment", "clean-up", "litter", "compost"],
    "space": ["star", "moon", "space", "astronomer", "planet",
              "rocket", "astronaut", "satellite", "galaxy", "comet", "meteor",
              "eclipse", "orbit"],
    "clothes": ["sandals", "cap", "shoes", "socks", "scarf", "boots", "gloves",
                "raincoat", "shirt", "coat", "dress", "uniform"],
    "home": ["kitchen", "bedroom", "bathroom", "garage", "canteen", "toilet",
             "attic", "porch", "hallway", "storeroom", "balcony"],
    "nature": ["rose", "leaf", "leaves", "seed", "root", "hibiscus", "lotus",
               "orchid", "sunflower", "tulip", "stem", "flower", "grass",
               "soil", "corn"],
    "toys": ["doll", "robot", "teddy", "kite", "drum", "balloon", "candle",
             "card", "gift"],
}


def _kw(topic: str) -> list[str]:
    return ART_KEYWORDS.get(topic, [])


def topics_for_text(text: str) -> str:
    """Return the art topic id that best matches ``text`` (else 'general')."""
    t = (text or "").lower()
    best, best_score = None, 0
    for topic, words in ART_KEYWORDS.items():
        score = sum(t.count(w) for w in words)
        if score > best_score:
            best, best_score = topic, score
    return best or "general"


# Photo subjects per topic, most specific phrase first.  ``query_for_text``
# scans a part's passage / items and picks the longest subject phrase it can
# find, so the search photo is tied to the actual content of the questions.
# A photo is only used when such a phrase is present in the article/questions
# (Round 13 follow-up: the generic topic fallback was removed so every picture
# stays related to the text it illustrates).
PHOTO_SUBJECTS = {
    "school": ["pencil case", "school bag", "school bus", "school bell",
               "classroom", "library", "homework", "assembly", "teacher",
               "pupils", "lesson", "school", "books", "crayon", "crayons",
               "recess", "gotong-royong", "clean-up", "notebook", "pencil",
               "ruler", "rubber", "eraser", "scissors"],
    "market": ["nasi lemak", "rambutan", "durian", "vegetables", "stall",
               "hawker", "seller", "market", "fruit", "fish", "buy", "coconut",
               "mango", "banana", "pineapple", "seafood"],
    "animals": ["proboscis monkey", "hornbill", "tapir", "pangolin",
                "elephant", "monkey", "tiger", "lion", "bird", "ranger",
                "zoo", "animal", "dog", "cat", "forest", "jungle", "giraffe",
                "kangaroo", "crocodile", "panda", "parrot", "rabbit", "hamster",
                "turtle", "duck", "lizard", "spider", "frog", "ant", "bee",
                "butterfly", "snake", "owl", "bear", "wolf", "fox", "zebra",
                "hippo", "octopus", "dolphin", "seal", "whale", "swan",
                "tortoise", "mouse", "rat", "cock", "crow", "hare", "deer",
                "hen", "chick", "rooster", "duckling", "jellyfish",
                "seahorse", "starfish", "crab", "shark"],
    "river": ["tadpole", "riverbank", "river", "stream", "fish"],
    "farm": ["padi", "chicken", "chick", "rooster", "hen", "goat", "sheep",
             "cow", "horse", "donkey", "farmer", "farm", "kampung", "garden"],
    "food": ["nasi lemak", "satay", "roti", "kuih", "curry", "noodles",
             "soup", "rice", "breakfast", "cake", "food", "lasagna",
             "pancake", "sandwich", "salad", "ice cream", "fried chicken",
             "sambal", "laksa", "milk", "bread", "egg", "jam", "juice",
             "cup", "plate", "bowl", "spoon", "fork", "toast", "cereal",
             "sausage", "corn", "cookies", "feast", "porridge", "omelette",
             "pastry", "cheese", "pie"],
    "festival": ["lion dance", "red packet", "mooncake", "lantern",
                 "dragon", "festival", "new year", "celebrate", "deepavali",
                 "hari raya", "christmas", "diwali", "parade", "greeting"],
    "town": ["twin towers", "batu caves", "kuala lumpur", "skyscraper",
             "penang", "landmark", "tower", "city", "town", "tourist",
             "mosque", "temple"],
    "transport": ["funicular", "monorail", "ferry", "lorry", "bicycle",
                  "train", "bus", "car", "transport", "ticket", "airplane",
                  "aeroplane", "helicopter", "ship", "boat"],
    "people": ["firefighter", "headmaster", "engineer", "doctor", "nurse",
               "teacher", "pilot", "chef", "job", "work", "dentist",
               "police", "veterinarian"],
    "rain": ["raincoat", "umbrella", "flood", "storm", "monsoon", "rain",
             "cloud", "boots", "thunder", "lightning", "sun", "wind",
             "rainbow", "puddle", "frost"],
    "sea": ["fisherman", "coral", "beach", "island", "boat", "sea", "ocean",
            "seashell", "sandcastle", "lighthouse", "crab", "shark", "whale",
            "starfish", "octopus", "dolphin", "turtle", "seal", "jellyfish",
            "seahorse", "sand", "wave", "shell"],
    "recycle": ["recycling", "rubbish", "bottles", "waste", "bin", "litter",
                "compost"],
    "space": ["astronomer", "planet", "moon", "star", "space", "rocket",
              "astronaut", "satellite", "galaxy", "comet", "meteor",
              "eclipse", "orbit"],
    "clothes": ["sandals", "sandal", "cap", "shoes", "shoe", "socks", "sock",
                "scarf", "boots", "gloves", "raincoat", "shirt", "coat",
                "dress", "uniform"],
    "home": ["kitchen", "bedroom", "bathroom", "garage", "canteen", "toilet",
             "attic", "porch", "hallway", "storeroom", "balcony"],
    "nature": ["hibiscus", "sunflower", "orchid", "lotus", "tulip", "rose",
               "leaf", "leaves", "seed", "root", "stem", "flower", "grass",
               "soil", "corn"],
    "toys": ["doll", "robot", "teddy", "kite", "drum", "balloon", "candle",
             "gift", "card"],
}

_TAG = re.compile(r"\b(?:the|a|an|his|her|their|my|your|our)\b\s*", re.I)


# Display keyword shown as a one-line hint above a part's passage (Parts 2
# and 3), derived from the detected topic.  Empty keeps the line hidden.
TOPIC_HINT = {
    "school": "School",
    "market": "Market",
    "animals": "Animal",
    "river": "River",
    "farm": "Farm",
    "food": "Food",
    "festival": "Festival",
    "town": "Town",
    "transport": "Transport",
    "people": "People",
    "rain": "Rain",
    "sea": "Sea",
    "recycle": "Recycling",
    "space": "Space",
    "clothes": "Clothes",
    "home": "Home",
    "nature": "Nature",
    "toys": "Toys",
}


def hint_for_topic(topic: str) -> str:
    """Return the display keyword for a detected topic ('' when none)."""
    return TOPIC_HINT.get((topic or "").strip().lower(), "")


def query_for_text(text: str) -> str:
    """Pick the photo subject that best matches ``text``.

    The dominant topic wins first, then the most specific (longest) phrase
    within it, so the photo stays on the subject the questions are about even
    when the passage also mentions an unrelated longer phrase.  Returns "" when
    no subject phrase occurs in the text — a picture is never used unless it is
    literally tied to the article/questions (Round 13 follow-up).
    """
    t = (text or "").lower()
    dominant = topics_for_text(t)
    found: list[tuple[int, str, str]] = []   # (specificity, topic, phrase)
    for topic, phrases in PHOTO_SUBJECTS.items():
        for phrase in phrases:
            if re.search(rf"\b{re.escape(phrase)}", t):
                found.append((len(phrase), topic, phrase))
    if not found:
        return ""
    found.sort(key=lambda f: (f[1] != dominant, -f[0]))
    phrase = found[0][2]
    return re.sub(r"\s+", " ", _TAG.sub("", phrase)).strip() or phrase


# ---------------------------------------------------------------------------
# Wikimedia Commons photographs (with local cache)
# ---------------------------------------------------------------------------

def _spend(t0: float) -> None:
    """Charge wall-clock time against the per-process photo budget."""
    global _budget_left
    _budget_left -= time.monotonic() - t0


def _commons_thumbs(query: str, width: int = 480) -> list[tuple[str, str]]:
    """Search Commons for ``query``; returns [(thumb_url, license)] best-first."""
    t0 = time.monotonic()
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f'filetype:bitmap "{query}"',
        "gsrnamespace": 6,
        "gsrlimit": 5,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": str(width),
        "iiextmetadatafilter": "LicenseShortName",
        "format": "json",
    }
    url = _PHOTO_SOURCE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _PHOTO_UA})
    try:
        with urllib.request.urlopen(req, timeout=_PHOTO_TIMEOUT) as res:
            info = json.loads(res.read().decode("utf-8", "replace"))
    except Exception:
        _spend(t0)
        return []
    _spend(t0)
    best: list[tuple[str, str]] = []
    pages = (info.get("query") or {}).get("pages") or {}
    if isinstance(pages, dict):
        pages = pages.values()
    for page in pages:
        ii = (page.get("imageinfo") or [{}])[0]
        thumb = ii.get("thumburl") or ii.get("url")
        if not thumb or ii.get("mime") != "image/jpeg":
            continue
        lic = ((ii.get("extmetadata") or {}).get("LicenseShortName")
               or {}).get("value", "")
        best.append((thumb, lic))
    # prefer clearly-free licences, then keep relevance order
    free = [b for b in best if re.search(r"public domain|cc0|cc by", b[1], re.I)]
    return free + [b for b in best if b not in free]


def _download(url: str) -> bytes | None:
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _PHOTO_UA})
        with urllib.request.urlopen(req, timeout=_PHOTO_TIMEOUT) as res:
            data = res.read(_PHOTO_MAX_BYTES + 1)
    except Exception:
        _spend(t0)
        return None
    _spend(t0)
    if len(data) > _PHOTO_MAX_BYTES or not data.startswith(b"\xff\xd8\xff"):
        return None
    return data


def photo_bytes(query: str, cache_dir: str | None = None,
                allow_fetch: bool = True) -> bytes | None:
    """Return a cached (or freshly downloaded) JPEG photo for ``query``.

    With ``allow_fetch=False`` only the on-disk cache is consulted (used for
    the instant first preview render).  Returns None on any network / search
    failure so the caller renders the part without a picture.  Fetching happens
    only once per query; the JPEG is stored under the app data dir.  The
    per-process wall-clock budget caps how long a paper generator can spend
    hunting for photos, so generation stays fast even on a blackholed network.
    """
    global _budget_left
    q = (query or "").strip()
    if not q or q in _failed_queries:
        return None
    cache_dir = cache_dir or _photo_cache_dir()
    key = hashlib.sha1(q.encode("utf-8")).hexdigest()[:20]
    path = os.path.join(cache_dir, key + ".jpg")
    if os.path.exists(path):
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except OSError:
            pass
    if not allow_fetch or _OFFLINE or _budget_left <= 0:
        return None
    # The budget is a shared *deadline* (entry wall-clock + seconds left), not
    # a counter each worker thread races to drain.  Siblings that start a
    # batch together all fit inside the same window, so a slow first query no
    # longer starves the paper's other topics; individual requests stay capped
    # by the socket timeout, and once the deadline passes later sequential
    # fetches stop (the blackholed-network guard).  Round 15 fix.
    deadline = time.monotonic() + max(_budget_left, 0.0)
    t0 = time.monotonic()
    try:
        data = None
        for thumb_url, _lic in _commons_thumbs(q):
            if time.monotonic() >= deadline:
                break
            data = _download(thumb_url)
            if data:
                break
    except Exception:
        data = None
    _spend(t0)
    if not data:
        _failed_queries.add(q)     # don't retry this query in this process
        return None
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError:
        pass
    return data


def reset_photo_budget() -> None:
    """Give the next photo batch a fresh budget.

    The per-process budget protects a one-shot CLI run, but the GUI is long
    lived and regenerates often — each background batch should get its own
    bounded budget (and retry queries that failed on a previous batch).
    """
    global _budget_left
    _budget_left = _PHOTO_BUDGET_SECS
    _failed_queries.clear()


def fetch_photos(queries, cache_dir: str | None = None,
                 workers: int = 4) -> dict[str, bytes | None]:
    """Warm the photo cache for many queries in parallel.

    Runs the (network-bound) Commons searches on a small thread pool so a
    paper with several pictures does not pay their latency one after another.
    The shared wall-clock budget still caps total time.  Returns a
    ``{query: jpeg_or_None}`` mapping (also useful to tests / callers).
    """
    qs = [q for q in dict.fromkeys(queries) if q and q.strip()]
    if not qs or _OFFLINE:
        return {q: None for q in qs}
    from concurrent.futures import ThreadPoolExecutor, wait

    out: dict[str, bytes | None] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(qs)))) as ex:
        futs = {ex.submit(photo_bytes, q, cache_dir): q for q in qs}
        wait(futs, timeout=_PHOTO_BUDGET_SECS + _PHOTO_TIMEOUT)
        for fut, q in futs.items():
            try:
                out[q] = fut.result(timeout=0)
            except Exception:
                out[q] = None
    return out


def image_dims(data: bytes) -> tuple[int, int] | None:
    """Read (width, height) from a JPEG or PNG byte blob, else None."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        import struct
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = (data[i + 2] << 8) | data[i + 3]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return ((data[i + 5] << 8) | data[i + 6],
                        (data[i + 7] << 8) | data[i + 8])
            i += 2 + length
    return None


def photo_candidates(part) -> list[str]:
    """Photo queries to try for a part, most specific first.

    Only the part's own phrase-derived ``photo_query`` is used; when the
    article or questions contain no matching subject the picture is skipped
    rather than showing something unrelated (Round 13 follow-up).
    """
    out: list[str] = []
    q = getattr(part, "photo_query", "") or ""
    if q:
        out.append(q)
    return out


def picture_html(part, allow_fetch: bool = True) -> str:
    """HTML for a part illustration: an embedded Wikipedia/Commons photo.

    No SVG stand-ins: if no photo is available (offline / fetch still running)
    a clean captioned placeholder keeps the layout stable, and the live preview
    swaps in the photograph as soon as the background fetch finishes.
    """
    for q in photo_candidates(part):
        data = photo_bytes(q, allow_fetch=allow_fetch)
        if data:
            import base64
            b64 = base64.b64encode(data).decode("ascii")
            alt = _esc_attr(q)
            return (f'<img class="pic-img" src="data:image/jpeg;base64,{b64}" '
                   f'alt="{alt}"/>')
    topic = getattr(part, "topic", "") or "general"
    return (f'<div class="pic-ph" aria-label="photo placeholder {_esc_attr(topic)}">'
            f'<div class="pic-ph-topic">{_esc_attr(topic.title())}</div>'
            f'<div class="pic-ph-note">Photo available online after a refresh '
            f'(Wikipedia, Commons).</div></div>')


def _esc_attr(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")