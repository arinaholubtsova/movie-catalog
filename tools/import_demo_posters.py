"""Fetch catalog film posters from their public TMDB movie pages."""
import html
import re
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "frontend" / "public" / "posters"
MOVIES = {
    "interstellar": "/movie/157336-interstellar",
    "arrival": "/movie/329865-arrival",
    "the-martian": "/movie/286217-the-martian",
    "inception": "/movie/27205-inception",
    "knives-out": "/movie/546554-knives-out",
    "grand-budapest-hotel": "/movie/120467-the-grand-budapest-hotel",
    "la-la-land": "/movie/313369-la-la-land",
    "whiplash": "/movie/244786-whiplash",
    "the-dark-knight": "/movie/155-the-dark-knight",
    "spider-verse": "/movie/324857-spider-man-into-the-spider-verse",
    "parasite": "/movie/496243",
    "the-imitation-game": "/movie/205596-the-imitation-game",
    "dune-part-two": "/movie/693134-dune-part-two",
    "oppenheimer": "/movie/872585-oppenheimer",
    "everything-everywhere": "/movie/545611-everything-everywhere-all-at-once",
    "shawshank-redemption": "/movie/278-the-shawshank-redemption",
    "forrest-gump": "/movie/13-forrest-gump",
    "pulp-fiction": "/movie/680-pulp-fiction",
    "fellowship-of-the-ring": "/movie/120-the-lord-of-the-rings-the-fellowship-of-the-ring",
    "spirited-away": "/movie/129-spirited-away",
    "coco": "/movie/354912-coco",
    "silence-of-the-lambs": "/movie/274-the-silence-of-the-lambs",
    "get-out": "/movie/419430-get-out",
    "mad-max-fury-road": "/movie/76341-mad-max-fury-road",
    "the-matrix": "/movie/603-the-matrix",
    "amelie": "/movie/194-le-fabuleux-destin-d-amelie-poulain",
    "truman-show": "/movie/37165-the-truman-show",
}


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    source_lines = ["Catalog movie poster sources", "", "Posters and movie metadata: TMDB (https://www.themoviedb.org).", "See https://developer.themoviedb.org/docs/faq for attribution terms.", ""]
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for slug, movie_path in MOVIES.items():
            page_url = f"https://www.themoviedb.org{movie_path}"
            page = client.get(page_url)
            page.raise_for_status()
            matches = re.findall(r'<meta property="og:image" content="([^"]+)"', page.text)
            poster_url = next((html.unescape(url) for url in matches if "/w500/" in url), None)
            if poster_url is None:
                raise RuntimeError(f"No poster on {page_url}")
            image = client.get(poster_url)
            image.raise_for_status()
            if image.headers.get("content-type", "").split(";")[0] not in ("image/jpeg", "image/png"):
                raise RuntimeError(f"Unexpected poster format for {slug}")
            extension = ".png" if image.headers["content-type"].startswith("image/png") else ".jpg"
            destination = DESTINATION / f"{slug}{extension}"
            destination.write_bytes(image.content)
            source_lines.append(f"- {slug}{extension}: {page_url} | {poster_url}")
            print(f"{slug}{extension}: {len(image.content)} bytes")
    (DESTINATION / "SOURCES.md").write_text("\n".join(source_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
