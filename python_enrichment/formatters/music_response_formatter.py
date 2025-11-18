"""
Music Response Formatter
Converts enrichment data into fast, readable facts for AI responses.
Prioritizes: members → albums → genres → years
Each fact <100 characters for LLM efficiency.
"""

from typing import Dict, Any, List, Optional


class MusicResponseFormatter:
    """Formats music enrichment data into concise facts."""

    MAX_FACT_LENGTH = 100
    MAX_FACTS = 5

    def format_artist(self, data: Dict[str, Any], members_data: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Format artist data into concise facts.

        Priority:
        1. Members (if available)
        2. Albums/Discography
        3. Genres
        4. Formation years
        5. Country/Origin

        Args:
            data: Raw artist enrichment data
            members_data: Optional band members data

        Returns:
            List of concise facts (<100 chars each)
        """
        facts = []

        # Priority 1: Formation/Type with year
        name = data.get("name", "")
        type_name = data.get("type_name", "").lower() or "artist"
        active_years = data.get("active_years", "")
        country = data.get("country", "")

        # Build formation fact
        formation_fact = f"{name} is a {type_name}"
        if country:
            formation_fact += f" from {country}"
        if active_years:
            formation_fact += f" active from {active_years}"
        elif data.get("formation_string"):
            # Extract year from formation string
            formation_str = data.get("formation_string", "")
            if "Formed" in formation_str or "formed" in formation_str:
                # Extract year
                parts = formation_str.split()
                for part in parts:
                    if part.isdigit() and len(part) == 4:
                        formation_fact += f" formed in {part}"
                        break

        if len(formation_fact) <= self.MAX_FACT_LENGTH:
            facts.append(formation_fact)

        # Priority 2: Current members
        if members_data:
            current_members = members_data.get("current_members", [])
            if current_members:
                member_strings = []
                for member in current_members[:5]:  # Limit to 5 members
                    name_str = member.get("name", "")
                    role = member.get("role", "")
                    if role and role != "member":
                        # Truncate role if too long
                        role_short = role.split(",")[0]  # Take first role
                        member_str = f"{name_str} ({role_short})"
                    else:
                        member_str = name_str
                    member_strings.append(member_str)

                if member_strings:
                    members_fact = "Current members: " + ", ".join(member_strings)
                    # Truncate if too long
                    if len(members_fact) > self.MAX_FACT_LENGTH:
                        # Try with fewer members
                        for i in range(len(member_strings), 0, -1):
                            test_fact = "Current members: " + ", ".join(member_strings[:i])
                            if len(test_fact) <= self.MAX_FACT_LENGTH:
                                members_fact = test_fact
                                break
                        else:
                            # Still too long, truncate last member
                            members_fact = members_fact[:self.MAX_FACT_LENGTH - 3] + "..."
                    facts.append(members_fact)

        # Priority 3: Albums/Discography
        albums = data.get("albums", [])
        if albums:
            # Count studio albums vs total
            studio_albums = [a for a in albums if a.get("type", "").lower() in ["album", "studio album"]]
            if studio_albums:
                album_count = len(studio_albums)
                years = []
                for album in studio_albums[:3]:  # Get years from first 3 albums
                    year = album.get("year", "")
                    if year and year not in years:
                        years.append(year)

                albums_fact = f"Released {album_count} studio album"
                if album_count > 1:
                    albums_fact += "s"

                # Add year range if available
                if years:
                    year_range = f" ({years[0]}"
                    if len(years) > 1:
                        year_range += f"-{years[-1]}"
                    year_range += ")"
                    if len(albums_fact + year_range) <= self.MAX_FACT_LENGTH:
                        albums_fact += year_range

                # Add notable albums
                notable = []
                for album in studio_albums[:2]:
                    title = album.get("title", "")
                    year = album.get("year", "")
                    if title and year:
                        notable.append(f"{title} ({year})")

                if notable:
                    notable_str = ", ".join(notable)
                    if len(albums_fact + ", including " + notable_str) <= self.MAX_FACT_LENGTH:
                        albums_fact += ", including " + notable_str
                    elif len(albums_fact + " (" + notable_str + ")") <= self.MAX_FACT_LENGTH:
                        albums_fact += " (" + notable_str + ")"

                if len(albums_fact) <= self.MAX_FACT_LENGTH:
                    facts.append(albums_fact)

        # Priority 4: Genres
        genres = data.get("genres", [])
        if genres:
            genres_str = ", ".join(genres[:5])  # Limit to 5 genres
            genres_fact = f"Genres: {genres_str}"
            if len(genres_fact) > self.MAX_FACT_LENGTH:
                # Truncate genres
                for i in range(len(genres), 0, -1):
                    test_fact = f"Genres: {', '.join(genres[:i])}"
                    if len(test_fact) <= self.MAX_FACT_LENGTH:
                        genres_fact = test_fact
                        break
                else:
                    genres_fact = genres_fact[:self.MAX_FACT_LENGTH - 3] + "..."
            facts.append(genres_fact)

        # Limit total facts
        return facts[:self.MAX_FACTS]

    def format_album(self, data: Dict[str, Any], credits_data: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Format album data into concise facts.

        Priority:
        1. Title, artist, release date
        2. Producer/Production credits
        3. Track count and duration
        4. Notable tracks

        Args:
            data: Raw album enrichment data
            credits_data: Optional production credits data

        Returns:
            List of concise facts (<100 chars each)
        """
        facts = []

        # Priority 1: Title, artist, release date
        title = data.get("title", "")
        artist = data.get("artist", "")
        year = data.get("year", "")
        release_date = data.get("release_date", "")

        if title and artist:
            album_fact = f"{title} is {artist}'s"
            if data.get("album_number"):
                album_num = data.get("album_number")
                if isinstance(album_num, int):
                    ordinal = self._ordinal(album_num)
                    album_fact += f" {ordinal} studio album"
                else:
                    album_fact += " studio album"
            else:
                album_fact += " studio album"

            # Add release date
            if release_date:
                album_fact += f", released {release_date}"
            elif year:
                album_fact += f", released {year}"

            if len(album_fact) <= self.MAX_FACT_LENGTH:
                facts.append(album_fact)

        # Priority 2: Producer/Production
        if credits_data:
            producers = credits_data.get("producers", [])
            if producers:
                producers_str = ", ".join(producers[:2])  # Limit to 2
                producer_fact = f"Producer: {producers_str}"
                if len(producer_fact) <= self.MAX_FACT_LENGTH:
                    facts.append(producer_fact)

            studios = credits_data.get("studios", [])
            if studios:
                studios_str = ", ".join(studios[:1])  # Limit to 1
                studio_fact = f"Recorded at: {studios_str}"
                if len(studio_fact) <= self.MAX_FACT_LENGTH:
                    facts.append(studio_fact)

        # Priority 3: Track count and duration
        tracks = data.get("tracks", [])
        if tracks:
            track_count = len(tracks)
            total_duration = data.get("total_duration", "")
            
            track_fact = f"{track_count} track"
            if track_count > 1:
                track_fact += "s"
            
            if total_duration:
                track_fact += f", {total_duration} total"
            
            if len(track_fact) <= self.MAX_FACT_LENGTH:
                facts.append(track_fact)

        # Priority 4: Notable tracks
        if tracks:
            notable = []
            for track in tracks[:3]:  # First 3 tracks or singles
                track_title = track.get("title", "")
                if track_title:
                    notable.append(track_title)

            if notable:
                notable_fact = f"Notable tracks: {', '.join(notable)}"
                if len(notable_fact) > self.MAX_FACT_LENGTH:
                    # Reduce number of tracks
                    for i in range(len(notable), 0, -1):
                        test_fact = f"Tracks: {', '.join(notable[:i])}"
                        if len(test_fact) <= self.MAX_FACT_LENGTH:
                            notable_fact = test_fact
                            break
                    else:
                        notable_fact = notable_fact[:self.MAX_FACT_LENGTH - 3] + "..."
                facts.append(notable_fact)

        # Limit total facts
        return facts[:self.MAX_FACTS]

    def format_track(self, data: Dict[str, Any]) -> List[str]:
        """
        Format track data into concise facts.

        Priority:
        1. Title, artist, album
        2. Duration
        3. Writers/Composers
        4. Year

        Args:
            data: Raw track enrichment data

        Returns:
            List of concise facts (<100 chars each)
        """
        facts = []

        # Priority 1: Title, artist, album
        title = data.get("title", "")
        artist = data.get("artist", "")
        album = data.get("album", "")
        year = data.get("year", "")

        if title and artist:
            track_fact = f'"{title}" is a track by {artist}'
            if album and year:
                track_fact += f" from {album} ({year})"
            elif album:
                track_fact += f" from {album}"
            elif year:
                track_fact += f" ({year})"

            if len(track_fact) <= self.MAX_FACT_LENGTH:
                facts.append(track_fact)

        # Priority 2: Duration
        duration = data.get("duration", "")
        if duration:
            duration_fact = f"Length: {duration}"
            if len(duration_fact) <= self.MAX_FACT_LENGTH:
                facts.append(duration_fact)

        # Priority 3: Writers/Composers
        writers = data.get("writers", [])
        if writers:
            writers_str = ", ".join(writers[:2])  # Limit to 2
            writers_fact = f"Written by: {writers_str}"
            if len(writers_fact) <= self.MAX_FACT_LENGTH:
                facts.append(writers_fact)

        # Priority 4: Genre
        genre = data.get("genre", "")
        if genre:
            genre_fact = f"Genre: {genre}"
            if len(genre_fact) <= self.MAX_FACT_LENGTH:
                facts.append(genre_fact)

        # Limit total facts
        return facts[:self.MAX_FACTS]

    def _ordinal(self, n: int) -> str:
        """Convert number to ordinal string (1st, 2nd, 3rd, etc.)."""
        if 10 <= n % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    def format_combined(self, artist_data: Dict[str, Any], 
                       members_data: Optional[Dict[str, Any]] = None,
                       albums_data: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """
        Format combined artist data with members and albums.

        Args:
            artist_data: Base artist data
            members_data: Optional band members data
            albums_data: Optional albums list

        Returns:
            List of formatted facts
        """
        # Start with artist facts
        facts = self.format_artist(artist_data, members_data)

        # Add albums summary if available and space allows
        if albums_data and len(facts) < self.MAX_FACTS:
            # Already handled in format_artist if albums are in artist_data
            pass

        return facts[:self.MAX_FACTS]


# Global instance
_formatter: Optional[MusicResponseFormatter] = None


def get_formatter() -> MusicResponseFormatter:
    """Get or create global formatter instance."""
    global _formatter
    if _formatter is None:
        _formatter = MusicResponseFormatter()
    return _formatter


def format_artist_response(data: Dict[str, Any], members_data: Optional[Dict[str, Any]] = None) -> List[str]:
    """Convenience function to format artist response."""
    formatter = get_formatter()
    return formatter.format_artist(data, members_data)


def format_album_response(data: Dict[str, Any], credits_data: Optional[Dict[str, Any]] = None) -> List[str]:
    """Convenience function to format album response."""
    formatter = get_formatter()
    return formatter.format_album(data, credits_data)


def format_track_response(data: Dict[str, Any]) -> List[str]:
    """Convenience function to format track response."""
    formatter = get_formatter()
    return formatter.format_track(data)

