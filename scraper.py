import re
import requests
from bs4 import BeautifulSoup

TARGET_URL = "https://www.jagobd.com/"
OUTPUT_FILE = "playlist.m3u"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def extract_m3u8(text):
    pattern = r'(https?:\/\/[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'
    return list(set(re.findall(pattern, text)))

def scrape_page(url):
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        text = r.text
        soup = BeautifulSoup(text, "html.parser")

        # Extract .m3u8 from raw html
        urls = extract_m3u8(text)

        # Find related internal channel pages
        links = soup.find_all("a", href=True)
        subpages = []
        for link in links:
            href = link["href"]
            if "/tvs/" in href or "/live/" in href or "/channel" in href:
                full = requests.compat.urljoin(url, href)
                subpages.append(full)

        # Crawl sub-pages for more m3u8s
        for sp in list(set(subpages))[:30]:
            try:
                sub = requests.get(sp, headers=headers, timeout=10).text
                urls += extract_m3u8(sub)
            except:
                pass

        return list(set(urls))

    except Exception:
        return []

def build_m3u(entries):
    lines = ["#EXTM3U"]
    for i, url in enumerate(entries, start=1):
        name = f"Channel_{i}"
        lines.append(f'#EXTINF:-1 group-title="Live",{name}')
        lines.append(url)
    return "\n".join(lines) + "\n"

def main():
    urls = scrape_page(TARGET_URL)
    if not urls:
        print("No streams found.")
        return

    content = build_m3u(urls)

    # Write playlist
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print("Playlist updated:", OUTPUT_FILE)
    print("Total channels:", len(urls))

if __name__ == "__main__":
    main()
