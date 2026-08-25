import requests

url = "https://universe.roboflow.com/ds/y9sxtlKXh8?key=ePuI9ala2H"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}
response = requests.get(url, headers=headers)

if response.status_code == 200:
    with open("dataset.zip", "wb") as f:
        f.write(response.content)
    print("Downloaded successfully!")
else:
    print(f"Failed to download. Status code: {response.status_code}")
    print(response.text[:200])
