package server

import (
	"io/fs"
	"net/http"
	"strings"
)

// setCacheHeaders sets Cache-Control based on file path.
// Vite content-hashed assets (under assets/) are immutable.
// index.html must always be revalidated.
func setCacheHeaders(w http.ResponseWriter, path string) {
	if strings.HasPrefix(path, "assets/") {
		w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
	} else {
		w.Header().Set("Cache-Control", "no-cache")
	}
}

// spaHandler serves static files from the given filesystem, falling back
// to index.html for client-side routing. API and health routes should be
// registered before this catch-all.
func spaHandler(fsys fs.FS) http.Handler {
	fileServer := http.FileServer(http.FS(fsys))

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Don't serve SPA for API routes.
		if strings.HasPrefix(r.URL.Path, "/api/") || r.URL.Path == "/healthz" {
			http.NotFound(w, r)
			return
		}

		// Try to serve the static file directly.
		path := r.URL.Path
		if path == "/" {
			path = "index.html"
		} else {
			path = strings.TrimPrefix(path, "/")
		}

		// Check if the file exists in the embedded FS.
		if _, err := fs.Stat(fsys, path); err == nil {
			setCacheHeaders(w, path)
			fileServer.ServeHTTP(w, r)
			return
		}

		// Fall back to index.html for client-side routing.
		w.Header().Set("Cache-Control", "no-cache")
		r.URL.Path = "/"
		fileServer.ServeHTTP(w, r)
	})
}
