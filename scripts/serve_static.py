"""Serve the audited local Pages export with the expected response headers."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class StaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory, **kwargs):
        self.root = Path(directory)
        self.headers_file = self.root / "_headers"
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self):
        for line in self.headers_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("  "):
                key, value = line.strip().split(": ", 1)
                self.send_header(key, value)
        super().end_headers()

    def send_head(self):
        translated = Path(self.translate_path(self.path))
        if not translated.resolve().is_relative_to(self.root) or translated.name == "_headers":
            return self.not_found()
        if translated.is_dir() and translated != self.root:
            return self.not_found()
        if translated != self.root and not translated.is_file():
            return self.not_found()
        return super().send_head()

    def not_found(self):
        path = self.root / "404.html"
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        return path.open("rb")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--directory", type=Path, default=Path("release/static"))
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not (directory / "_headers").is_file():
        parser.error("Build and audit the static export first.")
    handler = partial(StaticHandler, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Static study at http://127.0.0.1:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
