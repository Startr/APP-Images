import sys
from pathlib import Path
from unsplash_get import search, save_img
import zipfile

def download_images(word):
    # Get list of URLs
    urls = search(word)

    # Create directory
    directory = Path(word)
    directory.mkdir(exist_ok=True)

    # Save images
    for index, url in enumerate(urls, start=1):
        path = str(directory / f'{word}_{index:03}.jpg')
        status = save_img(url, path)
        print(f"{index:03}.{url} -> {path} ({status})")

    return directory

def create_zip(directory):
    zip_path = f"{directory}.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in directory.iterdir():
            zipf.write(file, file.name)
    return zip_path

def main(words):
    for word in words:
        directory = download_images(word)
        zip_path = create_zip(directory)
        print(f"Created zip file: {zip_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_images.py word1 word2 ...")
    else:
        words = sys.argv[1:]
        main(words)

