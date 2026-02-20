from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass


@dataclass
class IntegrationResult:
    ok: bool
    message: str


def _open_url(url: str) -> bool:
    try:
        webbrowser.open(url, new=2)
        return True
    except Exception:
        return False


def _http_get_json(url: str, params: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(full_url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload)


def open_spotify(query: str, access_token: str = "") -> IntegrationResult:
    query = (query or "").strip()
    if not query:
        opened = _open_url("https://open.spotify.com/")
        if opened:
            return IntegrationResult(True, "Opening Spotify. Enjoy. I will stay quiet in presence mode.")
        return IntegrationResult(False, "I couldn't launch Spotify in your browser right now.")

    if access_token:
        try:
            data = _http_get_json(
                "https://api.spotify.com/v1/search",
                {"q": query, "type": "track", "limit": "1"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            items = (data.get("tracks") or {}).get("items") or []
            if items:
                track = items[0]
                track_url = track.get("external_urls", {}).get("spotify", "https://open.spotify.com/")
                opened = _open_url(track_url)
                if not opened:
                    return IntegrationResult(False, "I found the track but couldn't launch Spotify.")
                artist = ", ".join(a.get("name", "") for a in track.get("artists", []))
                return IntegrationResult(True, f"Playing {track.get('name', 'that track')} by {artist}. I will stay quiet in presence mode.")
        except Exception:
            pass

    encoded = urllib.parse.quote_plus(query)
    opened = _open_url(f"https://open.spotify.com/search/{encoded}")
    if not opened:
        return IntegrationResult(False, f"I couldn't open Spotify search for {query} right now.")
    return IntegrationResult(True, f"Couldn't resolve an exact track, so I opened Spotify search results for {query}. I will stay quiet in presence mode.")


def _extract_title_artist_query(query: str) -> str:
    text = (query or "").strip()
    match = re.match(r"^watch\s+(.+?)\s+by\s+(.+)$", text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1).strip()} {match.group(2).strip()}"
    return text



def _resolve_youtube_video_id_without_key(query: str) -> str:
    full_url = f"https://www.youtube.com/results?{urllib.parse.urlencode({'search_query': query})}"
    request = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        html = response.read().decode("utf-8", errors="ignore")
    match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
    return match.group(1) if match else ""


def open_youtube(query: str, api_key: str = "") -> IntegrationResult:
    query = (query or "").strip()
    if not query:
        opened = _open_url("https://www.youtube.com/")
        if opened:
            return IntegrationResult(True, "Opening YouTube. I will stay quiet in presence mode.")
        return IntegrationResult(False, "I couldn't launch YouTube in your browser right now.")

    if api_key:
        try:
            data = _http_get_json(
                "https://www.googleapis.com/youtube/v3/search",
                {"part": "snippet", "q": query, "maxResults": "1", "type": "video", "key": api_key},
            )
            items = data.get("items") or []
            if items:
                video_id = items[0].get("id", {}).get("videoId")
                if video_id:
                    opened = _open_url(f"https://www.youtube.com/watch?v={video_id}")
                    if not opened:
                        return IntegrationResult(False, "I found a matching YouTube video but couldn't open it.")
                    return IntegrationResult(True, f"Opened the top YouTube video match for {query}. I will stay quiet in presence mode.")
        except Exception:
            pass

    parsed_query = _extract_title_artist_query(query)
    try:
        video_id = _resolve_youtube_video_id_without_key(parsed_query)
        if video_id:
            opened = _open_url(f"https://www.youtube.com/watch?v={video_id}")
            if not opened:
                return IntegrationResult(False, "I found a likely YouTube match but couldn't open it.")
            return IntegrationResult(True, f"Opened a best-effort YouTube video match for {parsed_query}. I will stay quiet in presence mode.")
    except Exception:
        pass

    encoded = urllib.parse.quote_plus(parsed_query)
    opened = _open_url(f"https://www.youtube.com/results?search_query={encoded}")
    if not opened:
        return IntegrationResult(False, f"I couldn't open YouTube search for {parsed_query} right now.")
    return IntegrationResult(True, f"Couldn't resolve an exact video, so I opened YouTube search results for {parsed_query}. I will stay quiet in presence mode.")


def weather_report(location: str) -> IntegrationResult:
    loc = (location or "").strip() or "my location"
    try:
        geo_data = _http_get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": loc, "count": "1", "language": "en", "format": "json"},
        )
        results = geo_data.get("results") or []
        if not results:
            return IntegrationResult(False, f"I couldn't find weather data for {loc}.")

        best = results[0]
        lat = str(best["latitude"])
        lon = str(best["longitude"])
        name = best.get("name", loc)
        country = best.get("country", "")

        weather_data = _http_get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,wind_speed_10m",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
            },
        )
        current = weather_data.get("current") or {}
        temp = current.get("temperature_2m")
        feels = current.get("apparent_temperature")
        wind = current.get("wind_speed_10m")
        where = f"{name}, {country}" if country else name
        return IntegrationResult(True, f"Weather in {where}: {temp}°F, feels like {feels}°F, wind {wind} mph.")
    except Exception as exc:
        return IntegrationResult(False, f"Weather lookup failed: {exc}")


def open_maps_directions(destination: str) -> IntegrationResult:
    place = (destination or "").strip()
    if not place:
        return IntegrationResult(False, "Tell me where you want directions to.")
    encoded = urllib.parse.quote_plus(place)
    opened = _open_url(f"https://www.google.com/maps/dir/?api=1&destination={encoded}")
    if not opened:
        return IntegrationResult(False, f"I couldn't open directions to {place} right now.")
    return IntegrationResult(True, f"Opening directions to {place}. I will stay quiet in presence mode.")
