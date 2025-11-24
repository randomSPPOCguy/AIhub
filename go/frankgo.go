package main

/*
#include <stdlib.h>
*/
import "C"

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
	"unsafe"

	_ "github.com/mattn/go-sqlite3"
)

var db *sql.DB
var goLogLevel = "INFO"

func init() {
	// Open SQLite database for caching
	path := os.Getenv("AIHUB_DB_PATH")
	if path == "" {
		path = "./data/aihub.db"
	}
	var err error
	db, err = sql.Open("sqlite3", path)
	if err != nil {
		log.Fatalf("Failed to open cache DB: %v", err)
	}
	// Create tables if not exist
	create := `
    CREATE TABLE IF NOT EXISTS music_cache (
        id INTEGER PRIMARY KEY,
        query TEXT UNIQUE,
        metadata JSON,
        timestamp DATETIME
    );
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY,
        session_id TEXT,
        username TEXT,
        message TEXT,
        timestamp DATETIME,
        expires_at DATETIME
    );
    CREATE TABLE IF NOT EXISTS artist_index (
        artist_name TEXT UNIQUE,
        mbid TEXT,
        genres JSON,
        albums JSON,
        latest_album JSON,
        latest_album_tracks JSON,
        updated_at DATETIME
    );`
	if _, err = db.Exec(create); err != nil {
		log.Fatalf("Failed to create tables: %v", err)
	}
	// Attempt to add latest_single column if it does not exist (safe to ignore if already present)
	_, _ = db.Exec("ALTER TABLE artist_index ADD COLUMN latest_single JSON")

	// Configure Go logging verbosity
	if lvl := strings.TrimSpace(os.Getenv("AIHUB_GO_LOG_LEVEL")); lvl != "" {
		goLogLevel = strings.ToUpper(lvl)
	}
	log.Printf("[GO][INFO] DB initialized at %s; LogLevel=%s", path, goLogLevel)
}

// main is required even when building as c-archive
func main() {}

// Logging helpers
func levelPriority(level string) int {
	switch strings.ToUpper(level) {
	case "ERROR":
		return 1
	case "WARN", "WARNING":
		return 2
	case "INFO", "SUCCESS":
		return 3
	case "DEBUG", "TRACE":
		return 4
	default:
		return 3
	}
}

func shouldLog(level string) bool {
	return levelPriority(level) <= levelPriority(goLogLevel)
}

func logMsg(level, format string, a ...interface{}) {
	if shouldLog(level) {
		log.Printf("[GO][%s] %s", strings.ToUpper(level), fmt.Sprintf(format, a...))
	}
}

// cleanMusicQuery normalizes queries by trimming punctuation and removing common phrases/entities,
// and extracting the likely core entity (e.g., "eminem") from queries like "what was eminems last album".
func cleanMusicQuery(query string) string {
	q := strings.Trim(query, "?!.,;:\\\"")
	lower := strings.ToLower(q)

	// Remove common question/filler and music-specific phrases
	for _, w := range []string{
		// question/filler
		"what was", "what is", "what's", "whats",
		"who is", "who's",
		"tell me about", "tell me",
		"can you tell me",
		"more info on", "info on", "more info", "more on",
		"give me", "show me",
		"ok frank", "okay frank", "okay, frank", "ok, frank", "hey frank",
		"ok", "okay", "hey",
		"please",
		"about",
		// music-specific
		"last album", "latest album", "new album",
		"album", "albums",
		"last song", "latest song",
		"song", "songs",
		"single", "track", "tracks",
		"release", "record", "records", "listen to", "you think", "recommend", "people", "last", "by",
	} {
		lower = strings.ReplaceAll(lower, w, " ")
	}

	// Strip possessive forms (e.g., "eminem's" -> "eminem")
	lower = strings.ReplaceAll(lower, "'s", " ")
	lower = strings.ReplaceAll(lower, "’s", " ")

	// Collapse whitespace
	fields := strings.Fields(lower)
	if len(fields) == 0 {
		return ""
	}
	cleaned := strings.Join(fields, " ")

	// Remove leading conversational fillers only at start (preserve "yeah yeah yeahs")
	{
		toks := strings.Fields(cleaned)
		for len(toks) > 0 {
			first := toks[0]
			if first == "yeah" || first == "yep" || first == "yup" || first == "ok" || first == "okay" || first == "hey" {
				// preserve band name "yeah yeah yeahs"
				if first == "yeah" && len(toks) >= 3 && toks[1] == "yeah" && strings.HasPrefix(toks[2], "yeah") {
					break
				}
				// drop the leading filler and continue
				toks = toks[1:]
				cleaned = strings.Join(toks, " ")
				continue
			}
			break
		}
	}

	// If a token like "u2s" appears, normalize to "u2" (short token with trailing 's' after digits)
	tokens := strings.Fields(cleaned)
	for i, t := range tokens {
		if len(t) <= 4 && strings.HasSuffix(t, "s") {
			// check if token contains any digit
			for _, ch := range t {
				if ch >= '0' && ch <= '9' {
					tokens[i] = strings.TrimSuffix(t, "s")
					break
				}
			}
		}
	}
	cleaned = strings.Join(tokens, " ")

	// If a single token remains like "eminems", singularize a simple trailing 's'
	tokens = strings.Fields(cleaned)
	if len(tokens) == 1 {
		t := tokens[0]
		if strings.HasSuffix(t, "s") && len(t) > 3 {
			t = strings.TrimSuffix(t, "s")
		}
		return t
	}

	return cleaned
}

// isMeaningfulEntity returns true if the normalized string contains at least
// one non-stopword token with letters (len > 2). This prevents running
// enrichment for generic prompts like "what's the most recent song".
func isMeaningfulEntity(normalized string) bool {
	toks := strings.Fields(strings.ToLower(strings.TrimSpace(normalized)))
	if len(toks) == 0 {
		return false
	}
	stop := map[string]struct{}{
		"what": {}, "whats": {}, "what's": {}, "who": {}, "who's": {}, "is": {}, "the": {}, "a": {}, "an": {},
		"of": {}, "for": {}, "to": {}, "and": {}, "or": {}, "can": {}, "you": {}, "tell": {}, "me": {}, "about": {},
		"please": {}, "new": {}, "latest": {}, "most": {}, "recent": {}, "that": {}, "just": {}, "came": {}, "out": {},
		"song": {}, "songs": {}, "album": {}, "albums": {}, "single": {}, "track": {}, "tracks": {}, "release": {}, "record": {},
		"ok": {}, "okay": {}, "hey": {}, "frank": {}, "well": {}, "was": {}, "were": {}, "last": {}, "by": {}, "i": {}, "we": {}, "my": {}, "your": {}, "our": {}, "should": {}, "would": {}, "recommend": {}, "listen": {}, "people": {}, "think": {}, "do": {},
	}
	for _, t := range toks {
		if _, bad := stop[t]; bad {
			continue
		}
		// consider tokens with any letter and length > 2 as potential entity
		alpha := false
		for _, ch := range t {
			if (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') {
				alpha = true
				break
			}
		}
		if alpha && len(t) > 2 {
			return true
		}
	}
	return false
}

func extractArtistCandidate(original string) string {
	s := strings.ToLower(original)
	// keep letters, digits, apostrophes and spaces; replace others with space
	cleaned := make([]rune, 0, len(s))
	for _, r := range s {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '\'' || r == ' ' {
			cleaned = append(cleaned, r)
		} else {
			cleaned = append(cleaned, ' ')
		}
	}
	toks := strings.Fields(string(cleaned))
	// strip possessive "'s" and "’s" from tokens to improve matching (e.g., "wet leg's" -> "wet leg")
	for i, t := range toks {
		if strings.HasSuffix(t, "'s") {
			toks[i] = strings.TrimSuffix(t, "'s")
		} else if strings.HasSuffix(t, "’s") {
			toks[i] = strings.TrimSuffix(t, "’s")
		}
	}
	if len(toks) == 0 {
		return ""
	}
	stop := map[string]struct{}{
		"what": {}, "whats": {}, "what's": {}, "who": {}, "who's": {}, "is": {}, "the": {}, "a": {}, "an": {},
		"of": {}, "for": {}, "to": {}, "and": {}, "or": {}, "can": {}, "you": {}, "tell": {}, "me": {}, "about": {},
		"please": {}, "new": {}, "latest": {}, "most": {}, "recent": {}, "that": {}, "just": {}, "came": {}, "out": {},
		"song": {}, "songs": {}, "album": {}, "albums": {}, "single": {}, "track": {}, "tracks": {}, "release": {}, "record": {},
		"ok": {}, "okay": {}, "hey": {}, "well": {}, "was": {}, "were": {}, "last": {}, "by": {}, "i": {}, "we": {}, "my": {}, "your": {}, "our": {}, "should": {}, "would": {}, "recommend": {}, "listen": {}, "people": {}, "think": {}, "do": {},
	}
	// pick the longest contiguous non-stopword window up to 3 tokens
	best := ""
	for i := 0; i < len(toks); i++ {
		if _, bad := stop[toks[i]]; bad {
			continue
		}
		for w := 3; w >= 1; w-- {
			if i+w > len(toks) {
				continue
			}
			good := true
			for j := i; j < i+w; j++ {
				if _, bad := stop[toks[j]]; bad {
					good = false
					break
				}
			}
			if good {
				cand := strings.Join(toks[i:i+w], " ")
				if len(cand) > len(best) {
					best = cand
				}
				break
			}
		}
	}
	// normalize very short digit+'s' tokens (e.g., u2s -> u2)
	if best != "" && len(best) <= 4 && strings.HasSuffix(best, "s") {
		hasDigit := false
		for _, ch := range best {
			if ch >= '0' && ch <= '9' {
				hasDigit = true
				break
			}
		}
		if hasDigit {
			best = strings.TrimSuffix(best, "s")
		}
	}
	return strings.TrimSpace(best)
}

type goResult struct {
	Domain   string          `json:"domain"`
	Query    string          `json:"query"`
	Summary  string          `json:"summary"`
	Metadata json.RawMessage `json:"metadata,omitempty"`
	Signal   string          `json:"signal"`
	CachedAt string          `json:"cached_at"`
}

func ttlHours() int {
	h := 24
	if s := os.Getenv("AIHUB_DB_TTL_HOURS"); s != "" {
		if v, err := strconv.Atoi(s); err == nil && v > 0 && v <= 168 {
			h = v
		}
	}
	return h
}

func cacheFresh(ts string) bool {
	if ts == "" {
		return false
	}
	t, err := time.Parse(time.RFC3339, ts)
	if err != nil {
		return false
	}
	maxAge := time.Duration(ttlHours()) * time.Hour
	return time.Since(t) < maxAge
}

//export go_music_query
func go_music_query(query *C.char, resultBuf *C.char, bufSize C.int) C.int {
	original := C.GoString(query)
	cleaned := cleanMusicQuery(original)

	// Try to extract a more precise artist candidate from the original utterance
	if cand := extractArtistCandidate(original); cand != "" && isMeaningfulEntity(cand) {
		logMsg("DEBUG", "artist candidate='%s' (overrides cleaned='%s')", cand, cleaned)
		cleaned = cand
	}

	logMsg("DEBUG", "music_query original='%s' cleaned='%s'", original, cleaned)
	if !isMeaningfulEntity(cleaned) {
		logMsg("WARN", "normalized query lacks entity; skipping enrichment")
		return handleQuery("music", "", resultBuf, bufSize)
	}
	return handleQuery("music", cleaned, resultBuf, bufSize)
}

//export go_sports_query
func go_sports_query(query *C.char, resultBuf *C.char, bufSize C.int) C.int {
	cleaned := cleanMusicQuery(C.GoString(query))
	return handleQuery("sports", cleaned, resultBuf, bufSize)
}

func handleQuery(domain, q string, resultBuf *C.char, bufSize C.int) C.int {
	// Early exit if no meaningful entity detected
	if strings.TrimSpace(q) == "" {
		now := time.Now().UTC().Format(time.RFC3339)
		payload := goResult{
			Domain:   domain,
			Query:    q,
			Summary:  "No entity detected; skipping enrichment",
			Metadata: json.RawMessage(`{}`),
			Signal:   "skip",
			CachedAt: now,
		}
		return writeResult(payload, resultBuf, bufSize)
	}

	// Check cache
	row := db.QueryRow("SELECT metadata, timestamp FROM music_cache WHERE query = ?", q)
	var metaText, ts string
	if err := row.Scan(&metaText, &ts); err == nil {
		if cacheFresh(ts) {
			payload := goResult{
				Domain:   domain,
				Query:    q,
				Summary:  "", // summary in metadata
				Metadata: json.RawMessage(metaText),
				Signal:   "cache",
				CachedAt: ts,
			}
			logMsg("INFO", "cache hit (fresh) query='%s' ts=%s", q, ts)
			return writeResult(payload, resultBuf, bufSize)
		}
		// stale cache; proceed to refresh via enrichment
	}

	// Perform enrichment
	logMsg("WARN", "cache miss or stale; enriching query='%s'", q)
	metadata, summary := enrichPipeline(q)

	// Store in cache
	metaJSON, _ := json.Marshal(metadata)
	now := time.Now().UTC().Format(time.RFC3339)
	_, _ = db.Exec(
		"INSERT OR REPLACE INTO music_cache(query, metadata, timestamp) VALUES(?,?,?)",
		q, string(metaJSON), now,
	)

	// Upsert summarized artist index ("madlib" cache)
	var genresJSON, albumsJSON, latestAlbumJSON, latestSingleJSON, tracksJSON []byte
	if v, ok := metadata["genres"]; ok {
		genresJSON, _ = json.Marshal(v)
	}
	if v, ok := metadata["albums"]; ok {
		albumsJSON, _ = json.Marshal(v)
	}
	{
		la := map[string]interface{}{}
		if v, ok := metadata["latest_album_title"]; ok {
			la["title"] = v
		}
		if v, ok := metadata["latest_album_date"]; ok {
			la["date"] = v
		}
		if v, ok := metadata["latest_album_id"]; ok {
			la["id"] = v
		}
		latestAlbumJSON, _ = json.Marshal(la)
	}
	{
		ls := map[string]interface{}{}
		if v, ok := metadata["latest_single_title"]; ok {
			ls["title"] = v
		}
		if v, ok := metadata["latest_single_date"]; ok {
			ls["date"] = v
		}
		latestSingleJSON, _ = json.Marshal(ls)
	}
	if v, ok := metadata["latest_album_tracks"]; ok {
		tracksJSON, _ = json.Marshal(v)
	}
	_, _ = db.Exec(
		"INSERT OR REPLACE INTO artist_index(artist_name, mbid, genres, albums, latest_album, latest_single, latest_album_tracks, updated_at) VALUES(?,?,?,?,?,?,?,?)",
		metadata["artist_name"], metadata["mbid"], string(genresJSON), string(albumsJSON), string(latestAlbumJSON), string(latestSingleJSON), string(tracksJSON), now,
	)

	logMsg("SUCCESS", "cached enrichment for query='%s' at %s", q, now)

	// Log enrichment for visibility
	log.Printf("[Enrichment] domain=%s query=%s summary=%s\n", domain, q, summary)

	payload := goResult{
		Domain:   domain,
		Query:    q,
		Summary:  summary,
		Metadata: metaJSON,
		Signal:   "enrich",
		CachedAt: now,
	}
	return writeResult(payload, resultBuf, bufSize)
}

// enrichPipeline implements MusicBrainz → Wikidata → Wikipedia lookup.
func enrichPipeline(query string) (map[string]interface{}, string) {
	metadata := make(map[string]interface{})
	logMsg("DEBUG", "enrichPipeline start query='%s'", query)

	// 1. MusicBrainz artist search
	mbURL := fmt.Sprintf("https://musicbrainz.org/ws/2/artist/?query=%s&fmt=json", url.QueryEscape(query))
	logMsg("DEBUG", "MusicBrainz URL: %s", mbURL)
	mbResp, err := http.Get(mbURL)
	if err != nil {
		metadata["musicbrainz_error"] = err.Error()
		logMsg("ERROR", "MusicBrainz request failed: %v", err)
		return metadata, "Error querying MusicBrainz"
	}
	defer mbResp.Body.Close()
	mbBody, _ := ioutil.ReadAll(mbResp.Body)
	var mbData struct {
		Artists []struct {
			ID    string `json:"id"`
			Name  string `json:"name"`
			Score int    `json:"score,omitempty"`
		} `json:"artists"`
	}
	json.Unmarshal(mbBody, &mbData)
	if len(mbData.Artists) == 0 {
		logMsg("WARN", "No MusicBrainz results for '%s'", query)
		return metadata, "No MusicBrainz results"
	}

	// choose best match by normalized name or highest score
	norm := func(s string) string {
		s = strings.ToLower(s)
		s = strings.ReplaceAll(s, "’", "")
		s = strings.ReplaceAll(s, "'", "")
		s = strings.ReplaceAll(s, " ", "")
		return s
	}
	candNorm := norm(query)
	bestIdx := 0
	bestScore := -1
	for i, a := range mbData.Artists {
		nameNorm := norm(a.Name)
		minLen := len(nameNorm)
		if len(candNorm) < minLen {
			minLen = len(candNorm)
		}
		containsOK := minLen >= 4 && (strings.Contains(nameNorm, candNorm) || strings.Contains(candNorm, nameNorm))
		match := nameNorm == candNorm || containsOK
		if match {
			bestIdx = i
			break
		}
		if a.Score > bestScore {
			bestScore = a.Score
			bestIdx = i
		}
	}
	mbid := mbData.Artists[bestIdx].ID
	metadata["mbid"] = mbid
	metadata["artist_name"] = mbData.Artists[bestIdx].Name

	// Fetch artist tags (genres)
	atURL := fmt.Sprintf("https://musicbrainz.org/ws/2/artist/%s?inc=tags&fmt=json", mbid)
	if atResp, err := http.Get(atURL); err == nil {
		defer atResp.Body.Close()
		atBody, _ := ioutil.ReadAll(atResp.Body)
		var atData struct {
			Tags []struct {
				Name  string `json:"name"`
				Count int    `json:"count"`
			} `json:"tags"`
		}
		if err := json.Unmarshal(atBody, &atData); err == nil && len(atData.Tags) > 0 {
			var genres []string
			for _, t := range atData.Tags {
				if t.Name != "" {
					genres = append(genres, t.Name)
				}
			}
			if len(genres) > 0 {
				metadata["genres"] = genres
			}
		}
	}

	// 1b. Find latest album via release-group browse
	rgURL := fmt.Sprintf("https://musicbrainz.org/ws/2/release-group?artist=%s&type=album&fmt=json&limit=100", mbid)
	rgResp, err := http.Get(rgURL)
	if err == nil {
		defer rgResp.Body.Close()
		rgBody, _ := ioutil.ReadAll(rgResp.Body)
		var rgData struct {
			ReleaseGroups []struct {
				ID               string `json:"id"`
				Title            string `json:"title"`
				FirstReleaseDate string `json:"first-release-date"`
			} `json:"release-groups"`
		}
		json.Unmarshal(rgBody, &rgData)
		// Build albums list
		albums := make([]map[string]string, 0, len(rgData.ReleaseGroups))
		latestTitle := ""
		latestDate := ""
		latestID := ""
		for _, rg := range rgData.ReleaseGroups {
			// collect album entry
			albums = append(albums, map[string]string{
				"title": rg.Title,
				"date":  rg.FirstReleaseDate,
			})
			if rg.FirstReleaseDate != "" && (latestDate == "" || rg.FirstReleaseDate > latestDate) {
				latestDate = rg.FirstReleaseDate
				latestTitle = rg.Title
				latestID = rg.ID
			}
		}
		// store albums list
		if len(albums) > 0 {
			metadata["albums"] = albums
		}
		if latestTitle != "" {
			metadata["latest_album_title"] = latestTitle
			metadata["latest_album_date"] = latestDate
			metadata["latest_album_id"] = latestID
			logMsg("INFO", "Latest album detected: %s (%s)", latestTitle, latestDate)
		}

		// Fetch latest album track list
		if latestID != "" {
			relURL := fmt.Sprintf("https://musicbrainz.org/ws/2/release?release-group=%s&fmt=json&limit=1", latestID)
			if relResp, err := http.Get(relURL); err == nil {
				defer relResp.Body.Close()
				relBody, _ := ioutil.ReadAll(relResp.Body)
				var relData struct {
					Releases []struct {
						ID string `json:"id"`
					} `json:"releases"`
				}
				if err := json.Unmarshal(relBody, &relData); err == nil && len(relData.Releases) > 0 {
					relID := relData.Releases[0].ID
					trURL := fmt.Sprintf("https://musicbrainz.org/ws/2/release/%s?inc=recordings&fmt=json", relID)
					if trResp, err2 := http.Get(trURL); err2 == nil {
						defer trResp.Body.Close()
						trBody, _ := ioutil.ReadAll(trResp.Body)
						var trData struct {
							Media []struct {
								Tracks []struct {
									Title string `json:"title"`
								} `json:"tracks"`
							} `json:"media"`
						}
						if err := json.Unmarshal(trBody, &trData); err == nil {
							var tracks []string
							for _, m := range trData.Media {
								for _, t := range m.Tracks {
									if t.Title != "" {
										tracks = append(tracks, t.Title)
									}
								}
							}
							if len(tracks) > 0 {
								metadata["latest_album_tracks"] = tracks
							}
						}
					}
				}
			}
		}
	}

	// 1c. Find latest single via release-group browse
	srgURL := fmt.Sprintf("https://musicbrainz.org/ws/2/release-group?artist=%s&type=single&fmt=json&limit=100", mbid)
	if srgResp, err := http.Get(srgURL); err == nil {
		defer srgResp.Body.Close()
		srgBody, _ := ioutil.ReadAll(srgResp.Body)
		var srgData struct {
			ReleaseGroups []struct {
				ID               string `json:"id"`
				Title            string `json:"title"`
				FirstReleaseDate string `json:"first-release-date"`
			} `json:"release-groups"`
		}
		if err := json.Unmarshal(srgBody, &srgData); err == nil {
			latestSingleTitle := ""
			latestSingleDate := ""
			for _, rg := range srgData.ReleaseGroups {
				if rg.FirstReleaseDate != "" && (latestSingleDate == "" || rg.FirstReleaseDate > latestSingleDate) {
					latestSingleDate = rg.FirstReleaseDate
					latestSingleTitle = rg.Title
				}
			}
			if latestSingleTitle != "" {
				metadata["latest_single_title"] = latestSingleTitle
				metadata["latest_single_date"] = latestSingleDate
				logMsg("INFO", "Latest single detected: %s (%s)", latestSingleTitle, latestSingleDate)
			}
		}
	}

	// 2. Wikidata search QID
	wdURL := fmt.Sprintf("https://www.wikidata.org/w/api.php?action=wbsearchentities&search=%s&language=en&format=json", url.QueryEscape(mbData.Artists[0].Name))
	wdResp, err := http.Get(wdURL)
	if err != nil {
		metadata["wikidata_error"] = err.Error()
	} else {
		defer wdResp.Body.Close()
		wdBody, _ := ioutil.ReadAll(wdResp.Body)
		var wdData struct {
			Search []struct {
				ID    string `json:"id"`
				Label string `json:"label"`
			} `json:"search"`
		}
		json.Unmarshal(wdBody, &wdData)
		if len(wdData.Search) > 0 {
			qid := wdData.Search[0].ID
			metadata["wikidata_qid"] = qid

			// 3. Wikidata sitelink
			entURL := fmt.Sprintf("https://www.wikidata.org/w/api.php?action=wbgetentities&ids=%s&props=sitelinks&format=json", qid)
			entResp, err2 := http.Get(entURL)
			if err2 == nil {
				defer entResp.Body.Close()
				entBody, _ := ioutil.ReadAll(entResp.Body)
				var entData struct {
					Entities map[string]struct {
						Sitelinks map[string]struct {
							Title string `json:"title"`
						} `json:"sitelinks"`
					} `json:"entities"`
				}
				json.Unmarshal(entBody, &entData)
				if en, ok := entData.Entities[qid].Sitelinks["enwiki"]; ok {
					metadata["wikipedia_title"] = en.Title

					// 4. Wikipedia summary
					wpURL := fmt.Sprintf("https://en.wikipedia.org/api/rest_v1/page/summary/%s", url.QueryEscape(en.Title))
					wpResp, err3 := http.Get(wpURL)
					if err3 == nil {
						defer wpResp.Body.Close()
						wpBody, _ := ioutil.ReadAll(wpResp.Body)
						var wpData struct {
							Extract string `json:"extract"`
						}
						json.Unmarshal(wpBody, &wpData)
						return metadata, wpData.Extract
					}
				}
			}
		}
	}

	// Fallback - prefer a useful summary (album and/or single)
	albumTitle, _ := metadata["latest_album_title"].(string)
	albumDate, _ := metadata["latest_album_date"].(string)
	singleTitle, _ := metadata["latest_single_title"].(string)
	singleDate, _ := metadata["latest_single_date"].(string)
	if albumTitle != "" && singleTitle != "" {
		summary := fmt.Sprintf("Latest album: %s (%s); Latest single: %s (%s)", albumTitle, albumDate, singleTitle, singleDate)
		return metadata, summary
	}
	if albumTitle != "" {
		summary := fmt.Sprintf("Latest album: %s (%s)", albumTitle, albumDate)
		return metadata, summary
	}
	if singleTitle != "" {
		summary := fmt.Sprintf("Latest single: %s (%s)", singleTitle, singleDate)
		return metadata, summary
	}
	summary := fmt.Sprintf("No summary available for '%s'", query)
	return metadata, summary
}

func writeResult(payload goResult, resultBuf *C.char, bufSize C.int) C.int {
	data, err := json.Marshal(payload)
	if err != nil {
		return -1
	}
	if len(data)+1 > int(bufSize) {
		return -1
	}
	buffer := (*[1 << 28]byte)(unsafe.Pointer(resultBuf))[:len(data)+1]
	copy(buffer, data)
	buffer[len(data)] = 0
	return 0
}
