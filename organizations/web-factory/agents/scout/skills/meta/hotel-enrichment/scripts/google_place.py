#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join("places." + f for f in (
    "id", "displayName", "formattedAddress", "internationalPhoneNumber",
    "nationalPhoneNumber", "websiteUri", "googleMapsUri", "rating",
    "userRatingCount", "location", "businessStatus", "regularOpeningHours",
))


def _emit(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _read_key():
    env = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if env:
        return env
    keyfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "secrets", "google_places.key")
    try:
        with open(keyfile, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def main():
    key = _read_key()
    if not key:
        _emit({"available": False, "reason": "no API key (secrets/google_places.key or env GOOGLE_PLACES_API_KEY) — Google Places unavailable; corroborate from the other allowlist sources"})
        return
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        _emit({"available": False, "reason": "usage: google_place.py <hotel name> <city>"})
        return
    body = json.dumps({"textQuery": query, "maxResultCount": 1}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": FIELD_MASK,
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        _emit({"available": False, "reason": f"Places API HTTP {e.code}: {detail}"})
        return
    except Exception as e:  # noqa: BLE001
        _emit({"available": False, "reason": f"Places API error: {e}"})
        return
    places = data.get("places") or []
    if not places:
        _emit({"available": True, "found": False, "query": query, "reason": "no Places match — check the hotel name/city"})
        return
    p = places[0]
    hours = p.get("regularOpeningHours") or {}
    _emit({
        "available": True,
        "found": True,
        "query": query,
        "source": "google_places_api",
        "name": (p.get("displayName") or {}).get("text"),
        "address": p.get("formattedAddress"),
        "phone": p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber"),
        "website": p.get("websiteUri"),
        "googleMapsUri": p.get("googleMapsUri"),
        "rating": p.get("rating"),
        "userRatingCount": p.get("userRatingCount"),
        "location": p.get("location"),
        "businessStatus": p.get("businessStatus"),
        "openingHours": hours.get("weekdayDescriptions"),
        "place_id": p.get("id"),
    })


if __name__ == "__main__":
    main()
