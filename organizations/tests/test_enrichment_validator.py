import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "web-factory" / "agents" / "scout"
    / "skills" / "meta" / "hotel-enrichment" / "scripts" / "validate_enrichment.py"
)
_spec = importlib.util.spec_from_file_location("validate_enrichment", _SCRIPT)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)


def _run(tmp_path: Path, text: str) -> int:
    doc = tmp_path / "enrichment.md"
    doc.write_text(text, encoding="utf-8")
    return validator.main(str(doc))


def test_prices_and_amounts_fail(tmp_path):
    assert _run(tmp_path, "- Suite Deluxe. Desde 2550 MXN/noche.") == 1
    assert _run(tmp_path, "- Deposito de MXN 5,000 a la llegada.") == 1
    assert _run(tmp_path, "- Rate from $120 per night.") == 1


def test_off_allowlist_sources_fail(tmp_path):
    assert _run(tmp_path, "- 3 plantas. (Hotels.com + ReservationDesk)") == 1
    assert _run(tmp_path, "- Piscina en azotea. (Tripadvisor + Expedia)") == 1


def test_volatile_ratings_fail(tmp_path):
    assert _run(tmp_path, "- Valoracion Google: 4.8/5 (36 resenas).") == 1


def test_clean_facts_pass(tmp_path):
    clean = (
        "# Enriquecimiento\n"
        "## Hechos verificados\n"
        "- Rooftop con vistas, ideal para una copa. (Oficial + Booking)\n"
        "- Check-in: 15:00-23:00. (Oficial + Booking)\n"
        "- Deposito de danos a la llegada, reembolsable tras inspeccion. (Booking)\n"
        "- Angel de la Independencia a 1.2 km, 14 min a pie. (Oficial + Booking)\n"
        "## Necesita revision humana\n"
        "- Restaurante sin nombre comercial establecido.\n"
    )
    assert _run(tmp_path, clean) == 0
