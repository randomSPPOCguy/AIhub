"""Pydantic models for enrichment service request/response schemas."""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class RoomNowPlaying(BaseModel):
    """Now playing information from room context."""

    artist: Optional[str] = None
    track: Optional[str] = None


class RoomContext(BaseModel):
    """Room context information."""

    id: Optional[str] = None
    topic: Optional[str] = None
    now_playing: Optional[RoomNowPlaying] = None


class SubjectHint(BaseModel):
    """Subject hint from caller."""

    name: str = Field(description="Subject name")
    type: str = Field(description="Subject type (artist, track, keyword, topic, etc.)")


class EnrichHints(BaseModel):
    """Hints for enrichment processing."""

    language: str = Field(default="en", description="Language code (e.g., 'en', 'es')")
    max_latency_ms: int = Field(default=200, description="Maximum acceptable latency in milliseconds")
    providers: List[str] = Field(
        default=["wikipedia", "musicbrainz"],
        description="List of provider names to use",
    )
    subjects: Optional[List[SubjectHint]] = Field(
        default=None,
        description="Optional pre-extracted subjects from caller (overrides auto-detection)",
    )


class EnrichRequest(BaseModel):
    """Request model for enrichment endpoint."""

    trace_id: Optional[str] = Field(default=None, description="Optional trace ID for request tracking")
    text: str = Field(..., description="Text to enrich (required)")
    room: Optional[RoomContext] = Field(default=None, description="Optional room context")
    hints: Optional[EnrichHints] = Field(default=None, description="Optional enrichment hints")

    class Config:
        """Pydantic config."""

        extra = "allow"  # Tolerate unknown fields for forward compatibility


class Subject(BaseModel):
    """Subject model for enrichment response."""

    name: str
    type: str = Field(description="Type of subject: 'artist', 'track', 'topic', etc.")
    ids: Dict[str, str] = Field(default_factory=dict, description="Canonical IDs (musicbrainz, wikidata, etc.)")
    urls: Dict[str, str] = Field(default_factory=dict, description="URLs (wikipedia, official, etc.)")


class Source(BaseModel):
    """Source model for enrichment response."""

    provider: str
    url: str
    title: str
    language: str


class Meta(BaseModel):
    """Metadata for enrichment response."""

    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    cache_status: str = Field(description="Cache status: 'hit', 'miss', or 'partial'")
    enrichment_time_ms: float = Field(description="Time taken for enrichment in milliseconds")
    partial: bool = Field(description="Whether enrichment is partial/incomplete")


class EnrichResponse(BaseModel):
    """Response model for enrichment endpoint."""

    version: str = Field(default="1.0", description="API version")
    trace_id: Optional[str] = Field(default=None, description="Trace ID from request")
    subjects: List[Dict[str, Any]] = Field(default_factory=list, description="List of enriched subjects")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    facts: List[str] = Field(default_factory=list, description="Extracted facts")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="List of sources")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Metadata about enrichment")

