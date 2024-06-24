from flask import Flask, render_template, request, send_file, url_for, jsonify, abort
from flask_caching import Cache
from PIL import Image
import os
from pathlib import Path
from unsplash_get import search, save_img
import logging
import random
import click

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Constants
THUMBNAIL_SIZE = (300, 300)
BASE_IMAGE_PATH = 'static/downloads'
CACHE_PATH = 'static/cache'

# Configure cache
app.config['CACHE_TYPE'] = 'SimpleCache'
cache = Cache(app)

def get_random_image(folder):
    folder_path = os.path.join(BASE_IMAGE_PATH, folder)
    images = [img for img in os.listdir(folder_path) if img.endswith(('jpg', 'jpeg', 'png, webp'))]
    return os.path.join(folder_path, random.choice(images))

def resize_image(image_path, width, height):
    cache_key = f"{image_path}_{width}_{height}"
    cached_image = cache.get(cache_key)
    
    if cached_image:
        return cached_image
    
    image = Image.open(image_path)
    resized_image = image.resize((width, height), Image.ANTIALIAS)
    cached_image_path = os.path.join(CACHE_PATH, f"{os.path.basename(image_path).split('.')[0]}_{width}x{height}.jpg")
    resized_image.save(cached_image_path)
    cache.set(cache_key, cached_image_path)
    return cached_image_path

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
        return '', 204
    prior_searches = get_prior_searches()
    return render_template('index.html', prior_searches=prior_searches)

@app.route('/random')
def random_image():
    folder = random.choice(os.listdir(BASE_IMAGE_PATH))
    image_path = get_random_image(folder)
    return send_file(image_path)

@app.route('/<int:width>x<int:height>')
def image_with_dimensions(width, height):
    folder = random.choice(os.listdir(BASE_IMAGE_PATH))
    image_path = get_random_image(folder)
    resized_image_path = resize_image(image_path, width, height)
    return send_file(resized_image_path)

@app.route('/folder/<folder>')
def random_image_from_folder(folder):
    if folder not in os.listdir(BASE_IMAGE_PATH):
        return "Folder not found", 404
    
    image_path = get_random_image(folder)
    return send_file(image_path)

@app.route('/progress/<word>', methods=['GET'])
def progress(word):
    """Serve the progress of thumbnails for the given word."""
    directory = Path(BASE_IMAGE_PATH) / word / 'thumbnails'
    thumbnails = list(directory.glob('*.webp'))
    thumbnail_urls = [url_for('static', filename=f'downloads/{word}/thumbnails/{thumbnail.name}') for thumbnail in thumbnails]
    return jsonify(thumbnail_urls)

@app.route('/imageset/<word>', methods=['GET'])
def image_set(word):
    """Display images in a set and provide download links."""
    directory = Path(BASE_IMAGE_PATH) / word
    if not directory.exists():
        abort(404)
    
    images = list(directory.glob('*.jpg'))
    image_urls = [url_for('static', filename=f'downloads/{word}/{image.name}') for image in images]
    return render_template('imageset.html', word=word, image_urls=image_urls)

@app.route('/download_image/<word>/<filename>', methods=['GET'])
def download_image(word, filename):
    """Serve individual image for download."""
    file_path = Path(BASE_IMAGE_PATH) / word / filename
    if not file_path.exists():
        abort(404)
    return send_file(file_path, as_attachment=True)

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
        thumbnail_path = thumbnail_dir / (Path(image_path).stem + '.webp')
        with Image.open(image_path) as img:
            img.thumbnail(THUMBNAIL_SIZE)
            img.save(thumbnail_path, 'WEBP')
            logging.info(f"Created thumbnail: {thumbnail_path}")
    except FileNotFoundError:
        logging.error(f"File not found: {image_path}")
    except Exception as e:
        logging.error(f"Error creating thumbnail for {image_path}: {e}")

def get_prior_searches():
    """Retrieve information about prior searches for display."""
    prior_searches = []
    download_path = Path(BASE_IMAGE_PATH)
    for directory in download_path.iterdir():
        if directory.is_dir():
            thumbnails = list((directory / 'thumbnails').glob('*.webp'))
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

def download_images(word):
    """Download images based on the search word and save them to a directory."""
    urls = search(word)
    directory = Path(BASE_IMAGE_PATH) / word
    directory.mkdir(exist_ok=True, parents=True)
    for index, url in enumerate(urls, start=1):
        path = str(directory / f'{word}_{index:03}.jpg')
        save_img(url, path)
        logging.info(f"Saved image: {path}")
        create_thumbnail_for_image(path)

@click.command()
def setup():
    """Sets up the necessary directory structure."""
    if not os.path.exists(BASE_IMAGE_PATH):
        os.makedirs(BASE_IMAGE_PATH)
        print(f"Created directory: {BASE_IMAGE_PATH}")
    
    if not os.path.exists(CACHE_PATH):
        os.makedirs(CACHE_PATH)
        print(f"Created directory: {CACHE_PATH}")
    
    print("Setup completed.")

if __name__ == '__main__':
    # Add setup command
    app.cli.add_command(setup)
    
    # Create cache and download directories if they don't exist
    if not os.path.exists(CACHE_PATH):
        os.makedirs(CACHE_PATH)
    if not os.path.exists(BASE_IMAGE_PATH):
        os.makedirs(BASE_IMAGE_PATH)
    
    # Create thumbnails for existing directories at startup
    download_path = Path(BASE_IMAGE_PATH)
    for directory in download_path.iterdir():
        if directory.is_dir():
            create_thumbnail(directory)

    app.run(debug=True)
