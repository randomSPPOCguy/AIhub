"""
Services package for AI Hub
Includes Wikipedia, MusicBrainz, and 5 new public APIs (no auth required)
"""

from .wikipedia_service import (
    get_wiki_summary,
    get_song_info,
    get_artist_info,
    get_album_info,
    search_wikipedia
)

from .musicbrainz_service import (
    mb_search_artist_by_name,
    mb_search_recording,
    mb_artist_genres_tags
)

# Import new service modules (for service_manager)
import sys
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

_base_dir = Path(__file__).parent


def _load_optional_service(module_name: str, relative_path: str):
    """
    Dynamically load service modules that currently live in a folder
    with spaces in its name ("we need to work on"). This ensures they
    can be imported as `services.<module_name>` just like first-party
    services.
    """
    module_key = f"{__name__}.{module_name}"
    file_path = _base_dir / relative_path

    if not file_path.exists():
        return None

    spec = spec_from_file_location(module_key, file_path)
    if spec and spec.loader:
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module_key] = module
        return module

    return None


noaa_weather_service = _load_optional_service(
    "noaa_weather_service", Path("we need to work on") / "noaa_weather_service.py"
)
tvmaze_service = _load_optional_service(
    "tvmaze_service", Path("we need to work on") / "tvmaze_service.py"
)
rest_countries_service = _load_optional_service(
    "rest_countries_service", Path("we need to work on") / "rest_countries_service.py"
)
open_library_service = _load_optional_service(
    "open_library_service", Path("we need to work on") / "open_library_service.py"
)
open_trivia_service = _load_optional_service(
    "open_trivia_service", Path("we need to work on") / "open_trivia_service.py"
)

__all__ = [
    'get_wiki_summary',
    'get_song_info',
    'get_artist_info',
    'get_album_info',
    'search_wikipedia',
    'mb_search_artist_by_name',
    'mb_search_recording',
    'mb_artist_genres_tags',
    'noaa_weather_service',
    'tvmaze_service',
    'rest_countries_service',
    'open_library_service',
    'open_trivia_service',
]

