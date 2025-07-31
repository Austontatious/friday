import requests
import os

def download_file(url: str, save_path: str = "/tmp") -> str:
    try:
        filename = os.path.basename(url.split("?")[0])
        dest_path = os.path.join(save_path, filename)

        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()

        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return f"✅ Downloaded to {dest_path}"

    except Exception as e:
        return f"❌ Failed to download {url}: {str(e)}"

