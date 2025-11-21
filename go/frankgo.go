package main

/*
#include <stdlib.h>
*/
import "C"

import (
	"encoding/json"
	"time"
	"unsafe"
)

type goResult struct {
	Domain   string `json:"domain"`
	Query    string `json:"query"`
	Summary  string `json:"summary"`
	Signal   string `json:"signal"`
	CachedAt string `json:"cached_at"`
}

//export go_music_query
func go_music_query(query *C.char, resultBuf *C.char, bufSize C.int) C.int {
	return handleQuery("music", C.GoString(query), resultBuf, bufSize)
}

//export go_sports_query
func go_sports_query(query *C.char, resultBuf *C.char, bufSize C.int) C.int {
	return handleQuery("sports", C.GoString(query), resultBuf, bufSize)
}

func handleQuery(domain string, q string, resultBuf *C.char, bufSize C.int) C.int {
	payload := goResult{
		Domain:   domain,
		Query:    q,
		Summary:  "stub response - replace with real logic",
		Signal:   "enrich",
		CachedAt: time.Now().UTC().Format(time.RFC3339),
	}
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

func main() {}
