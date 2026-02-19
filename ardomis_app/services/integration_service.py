from __future__ import annotations

import json
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass


@dataclass
class IntegrationResult:
    ok: bool
    message: str


def _open_url(url: str) -> None:
    webbrowser.open(url, new=2)


def _http_get_json(url: str, params: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(full_url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload)


def open_spotify(query: str, access_token: str = "") -> IntegrationResult:
    query = (query or "").strip()
    if not query:
        _open_url("https://open.spotify.com/")
        return IntegrationResult(True, "Opening Spotify. Enjoy. I will stay quiet in presence mode.")

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
                _open_url(track.get("external_urls", {}).get("spotify", "https://open.spotify.com/"))
                artist = ", ".join(a.get("name", "") for a in track.get("artists", []))
                return IntegrationResult(True, f"Playing {track.get('name', 'that track')} by {artist}. I will stay quiet in presence mode.")
        except Exception:
            pass

    encoded = urllib.parse.quote_plus(query)
    _open_url(f"https://open.spotify.com/search/{encoded}")
    return IntegrationResult(True, f"Opening Spotify results for {query}. I will stay quiet in presence mode.")


def open_youtube(query: str, api_key: str = "") -> IntegrationResult:
    query = (query or "").strip()
    if not query:
        _open_url("https://www.youtube.com/")
        return IntegrationResult(True, "Opening YouTube. I will stay quiet in presence mode.")

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
                    _open_url(f"https://www.youtube.com/watch?v={video_id}")
                    return IntegrationResult(True, f"Opening YouTube for {query}. I will stay quiet in presence mode.")
        except Exception:
            pass

    encoded = urllib.parse.quote_plus(query)
    _open_url(f"https://www.youtube.com/results?search_query={encoded}")
    return IntegrationResult(True, f"Opening YouTube search for {query}. I will stay quiet in presence mode.")


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
    _open_url(f"https://www.google.com/maps/dir/?api=1&destination={encoded}")
    return IntegrationResult(True, f"Opening directions to {place}. I will stay quiet in presence mode.")
