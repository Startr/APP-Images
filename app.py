#!/usr/bin/env python3

from flask import Flask, render_template, request, send_file, url_for, jsonify
from PIL import Image
import os
from pathlib import Path
from unsplash_get import search, save_img
import zipfile
import logging

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Constants
THUMBNAIL_SIZE = (150, 150)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        word = request.form['word']
        logging.info(f"Received word: {word}")
        try:
            download_images(word)
        except Exception as e:
            logging.error(f"Error downloading images: {e}")
            return str(e), 500
        # Instead of waiting for all images to download, we immediately return a response and update thumbnails via htmx
        return '', 204
    prior_searches = get_prior_searches()
    return render_template('index.html', prior_searches=prior_searches)

def download_images(word):
    """Download images based on the search word and save them to a directory."""
    urls = search(word)
    directory = Path('static/downloads') / word
    directory.mkdir(exist_ok=True, parents=True)
    for index, url in enumerate(urls, start=1):
        path = str(directory / f'{word}_{index:03}.jpg')
        save_img(url, path)
        logging.info(f"Saved image: {path}")
        create_thumbnail_for_image(path)

@app.route('/progress/<word>', methods=['GET'])
def progress(word):
    """Serve the progress of thumbnails for the given word."""
    directory = Path('static/downloads') / word / 'thumbnails'
    thumbnails = list(directory.glob('*.jpg'))
    thumbnail_urls = [url_for('static', filename=f'downloads/{word}/thumbnails/{thumbnail.name}') for thumbnail in thumbnails]
    return jsonify(thumbnail_urls)

def create_thumbnail(directory):
    """Create thumbnails for the images in the specified directory."""
    thumbnail_dir = directory / 'thumbnails'
    thumbnail_dir.mkdir(exist_ok=True)
    for image_path in directory.glob('*.jpg'):
        create_thumbnail_for_image(image_path)

def create_thumbnail_for_image(image_path):
    """Create a thumbnail for a single image."""
    try:
        thumbnail_dir = Path(image_path).parent / 'thumbnails'
        thumbnail_dir.mkdir(exist_ok=True)
        thumbnail_path = thumbnail_dir / Path(image_path).name
        with Image.open(image_path) as img:
            img.thumbnail(THUMBNAIL_SIZE)
            img.save(thumbnail_path)
            logging.info(f"Created thumbnail: {thumbnail_path}")
    except FileNotFoundError:
        logging.error(f"File not found: {image_path}")
    except Exception as e:
        logging.error(f"Error creating thumbnail for {image_path}: {e}")

def get_prior_searches():
    """Retrieve information about prior searches for display."""
    prior_searches = []
    download_path = Path('static/downloads')
    for directory in download_path.iterdir():
        if directory.is_dir():
            thumbnails = list((directory / 'thumbnails').glob('*.jpg'))
            thumbnail_urls = [url_for('static', filename=f'downloads/{directory.name}/thumbnails/{thumbnail.name}') for thumbnail in thumbnails]
            prior_searches.append({
                'word': directory.name,
                'zip_path': f'downloads/{directory.name}.zip',
                'thumbnail_urls': thumbnail_urls
            })
            logging.info(f"Processed prior search: {directory.name}")
    return prior_searches

@app.route('/download/<path:filename>')
def download_file(filename):
    """Serve the specified file for download."""
    return send_file(Path('static') / filename, as_attachment=True)

if __name__ == '__main__':
    # Create thumbnails for existing directories at startup
    download_path = Path('static/downloads')
    for directory in download_path.iterdir():
        if directory.is_dir():
            create_thumbnail(directory)
    app.run(debug=True)
