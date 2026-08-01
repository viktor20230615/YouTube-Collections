from datetime import (
    datetime, 
    timedelta, 
    timezone, 
)
import calendar, re


def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def format_date(iso_str):
    """Format UTC date into local date and time for display"""
    if not iso_str:
        return None
    
    try:
        dt_utc = parse_iso_datetime(iso_str)
        dt_local = dt_utc.astimezone()
        now_local = datetime.now().astimezone()
    except Exception as e:
        print(f"⚠️ format_date failed for {iso_str!r}: {e}")
        return iso_str

    deltadays = (now_local.date() - dt_local.date()).days
    timepart = dt_local.strftime('%H:%M')

    if deltadays == 0:
        return f"Today {timepart}"
    elif deltadays == 1:
        return f"Yesterday {timepart}"
    elif deltadays < 7:
        return f"{calendar.day_abbr[dt_local.weekday()]} {timepart}"
    elif dt_local.year == now_local.year:
        return dt_local.strftime('%b %d %H:%M')
    else:
        return dt_local.strftime('%Y %b %d %H:%M')


def format_seconds(seconds):
    if seconds is None:
        return None

    if seconds == 0:
        return 'Live'
    
    days = seconds // (24 * 3600)
    hours = (seconds % (24 * 3600)) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if days > 0:
        return f"{days}:{hours:02d}:{minutes:02d}:{secs:02d}"
    elif hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    elif minutes > 0:
        return f"{minutes}:{secs:02d}"
    else:
        return f"{secs}"


def is_after_cursor(published_at, id, cursor_published_at, cursor_id):
    return (
        published_at > cursor_published_at or
        (published_at == cursor_published_at and id > cursor_id)
    )


def is_after_with_offset(iso_str, reference_iso=None, offset_hours=0):
    dt = parse_iso_datetime(iso_str)

    if reference_iso is not None:
        reference_dt = parse_iso_datetime(reference_iso)
    else:
        reference_dt = datetime.now(timezone.utc)

    return dt > reference_dt - timedelta(hours=offset_hours)


LEADING_ARTICLE_RE = re.compile(r"^(a|an|the)\s+", re.IGNORECASE)

def normalize_string_start(value: str) -> str:
    value = value.strip()
    value = LEADING_ARTICLE_RE.sub("", value)
    return value.casefold()


# UNUSED but kept as potentially useful utility
def offset_datetime(iso_str=None, offset_hours=0):
    if iso_str:
        reference_dt = parse_iso_datetime(iso_str)
    else:
        reference_dt = datetime.now(timezone.utc)
    
    return reference_dt - timedelta(hours=offset_hours)


def parse_duration_to_seconds(iso_duration):
    """Parse YouTube ISO 8601 duration to seconds"""
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
    else:
        match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
        if match:
            days = int(match.group(1) or 0)
            hours = int(match.group(2) or 0)
            minutes = int(match.group(3) or 0)
            seconds = int(match.group(4) or 0)
            return days * 24 * 3600 + hours * 3600 + minutes * 60 + seconds
        elif iso_duration == 'P0D':
            return 0
        else:
            print(f"⚠️ parse_duration_to_seconds: no match for ISO string '{iso_duration}'")
            return None


def parse_iso_datetime(iso_str):
    """Parse ISO datetime strings with Z suffix and variable fractional seconds."""
    if not iso_str:
        return None

    s = iso_str.strip()

    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    if "." in s:
        main, frac_and_tz = s.split(".", 1)

        tz_pos = max(frac_and_tz.find("+"), frac_and_tz.find("-"))
        if tz_pos != -1:
            frac = frac_and_tz[:tz_pos]
            tz = frac_and_tz[tz_pos:]
        else:
            frac = frac_and_tz
            tz = ""

        frac = (frac[:6]).ljust(6, "0")
        s = f"{main}.{frac}{tz}"

    return datetime.fromisoformat(s)


ALLOWED_SORT_FIELDS = {"channel_name", "category_name", "subscribed_at", "refreshed_at"}
ALLOWED_DIRECTIONS = {"asc", "desc"}

def parse_sort_param(sort_param: str) -> list[dict[str, str]]:
    if not sort_param:
        return []

    sort_criteria = []

    for item in sort_param.split(','):
        if ':' not in item:
            continue

        field, direction = item.split(':', 1)
        field = field.strip().lower()
        direction = direction.strip().lower()

        if field not in ALLOWED_SORT_FIELDS or direction not in ALLOWED_DIRECTIONS:
            continue

        sort_criteria.append({
            'field': field,
            'direction': direction,
        })

    return sort_criteria
