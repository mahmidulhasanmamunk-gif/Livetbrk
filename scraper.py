import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.jagobd.com/"
API_URL = "https://www.jagobd.com/wp-json/jbgapi/v1/getplayer/?id="
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

OUTPUT_FILE = "playlist.m3u"

def get_channel_ids():
    r = requests.get(BASE_URL, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    ids = []

    for a in soup.find_all("a"):
        href = a.get("href", "")
        match = re.search(r'play\.php\?id=([\w-]+)', href)
        if match:
            ids.append(match.group(1))

    return list(set(ids))

def fetch_m3u8(channel_id):
    url = API_URL + channel_id
    r = requests.get(url, headers=HEADERS)
    
    if r.status_code != 200:
        return None

    data = r.json()

    if "stream_url" in data and data["stream_url"]:
        return data["stream_url"]

    return None

def build_m3u(urls):
    lines = ["#EXTM3U"]
    for name, url in urls.items():
        lines.append(f'#EXTINF:-1 group-title="Jagobd",{name}')
        lines.append(url)
    return "\n".join(lines) + "\n"

def main():
    ids = get_channel_ids()
    print("Found channel IDs:", len(ids))

    url_dict = {}

    for cid in ids:
        m3u8 = fetch_m3u8(cid)
        if m3u8:
            url_dict[cid] = m3u8

    print("Streams collected:", len(url_dict))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(build_m3u(url_dict))


if __name__ == "__main__":
    main()
