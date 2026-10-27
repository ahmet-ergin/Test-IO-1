"""Java/Gauge text helpers: safe string literals, identifiers, Gauge step text sanitising."""
import re
import unicodedata

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
JAVA_KEYWORDS = set("""abstract assert boolean break byte case catch char class const continue default do double else enum
extends final finally float for goto if implements import instanceof int interface long native new package private
protected public return short static strictfp super switch synchronized this throw throws transient try void volatile
while true false null var record yield sealed permits""".split())


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").translate(_TR)).encode("ascii", "ignore").decode()


def words(s: str) -> list:
    return re.findall(r"[A-Za-z0-9]+", ascii_fold(s))


def pascal(s: str) -> str:
    return "".join(w[:1].upper() + w[1:].lower() for w in words(s))


def camel(s: str) -> str:
    p = pascal(s)
    return p[:1].lower() + p[1:]


def const(s: str) -> str:
    return "_".join(w.upper() for w in words(s))


def jwords(s: str) -> list:
    """Like words() but also splits camelCase (transferButton -> transfer, Button)."""
    return [p for w in words(s) for p in re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", w)]


def jpascal(s: str) -> str:
    return "".join(w[:1].upper() + w[1:].lower() for w in jwords(s))


def jcamel(s: str) -> str:
    p = jpascal(s)
    return p[:1].lower() + p[1:]


def jconst(s: str) -> str:
    return "_".join(w.upper() for w in jwords(s))


def java_str(s: str, ascii_only: bool = False) -> str:
    """Java string literal. Never emits \\u escapes for quote/backslash/CR/LF (the lexer pre-processes \\u)."""
    out = []
    for ch in s or "":
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20 or o == 0x7F:
            out.append("\\%03o" % o)
        elif ascii_only and o > 0x7E:
            out.extend("\\u%04x" % u for u in _utf16(ch))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _utf16(ch: str):
    b = ch.encode("utf-16-be")
    return [int.from_bytes(b[i:i + 2], "big") for i in range(0, len(b), 2)]


def comment_safe(s: str) -> str:
    """Text for a // comment: single line, backslashes doubled so no \\u escape can form."""
    s = re.sub(r"[\r\n\u2028\u2029\x00-\x1f]+", " ", s or "")
    return s.replace("\\", "\\\\").strip()


def gauge_text(s: str, limit: int = 40) -> str:
    """Gauge step fragment: no quotes/angle brackets (would become parameters), single line."""
    s = re.sub(r'["<>\\`*#|]', " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit].strip()


def is_ident(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s or "")) and s not in JAVA_KEYWORDS


def is_package(s: str) -> bool:
    return bool(s) and all(is_ident(p) for p in s.split("."))


def is_fqcn(s: str) -> bool:
    return is_package(s) and "." in s and s.split(".")[-1][:1].isupper()


def simple(fqcn: str) -> str:
    return fqcn.rsplit(".", 1)[-1]


def pkg_of(fqcn: str) -> str:
    return fqcn.rsplit(".", 1)[0] if "." in fqcn else ""
