import re
import sys
from pathlib import Path

PRICE = re.compile(
    r"(?:\$|€|£)\s?\d|\d[\d.,]*\s?(?:MXN|EUR|USD|GBP|pesos?)\b"
    r"|\b(?:MXN|EUR|USD|GBP)\s?[\d.,]*\d"
    r"|(?:desde|from)\s+[\d.,]+"
    r"|[\d.,]+\s*(?:/|por\s|per\s)\s*(?:noche|night)",
    re.IGNORECASE,
)
FORBIDDEN_HOSTS = re.compile(
    r"reservationdesk|trivago|kayak|agoda|despegar|priceline"
    r"|tripadvisor|expedia|hotels\.com", re.IGNORECASE
)
VOLATILE = re.compile(r"(?:valoraci[oó]n|rating)\D{0,20}\d[\d.,]*\s*/\s*(?:5|10)", re.IGNORECASE)


def main(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8")
    failures: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        if PRICE.search(line):
            failures.append(f"L{number} PRICE/AMOUNT: {line.strip()[:100]}")
        if FORBIDDEN_HOSTS.search(line):
            failures.append(f"L{number} OFF-ALLOWLIST SOURCE: {line.strip()[:100]}")
        if VOLATILE.search(line):
            failures.append(f"L{number} VOLATILE RATING: {line.strip()[:100]}")
    if failures:
        print("ENRICHMENT VALIDATION FAILED — remove these before handoff:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("enrichment clean: no prices, no off-allowlist sources, no volatile ratings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "work/enrichment.md"))
