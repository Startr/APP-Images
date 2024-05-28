from flask import Flask, render_template, request, send_file, url_for, jsonify, abort, redirect
from PIL import Image
import os
from pathlib import Path
from unsplash_get import search, save_img
import zipfile
import logging
import boto3
import b2sdk.v1 as b2
from botocore.exceptions import NoCredentialsError
from flask_admin import Admin, BaseView, expose

# Environment variables
USE_CLOUD_STORAGE = os.getenv('USE_CLOUD_STORAGE', 'False').lower() in ('true', '1', 't')
CLOUD_STORAGE_PROVIDER = os.getenv('CLOUD_STORAGE_PROVIDER', 's3')
ACCESS_KEY = os.getenv('ACCESS_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
BUCKET_NAME = os.getenv('BUCKET_NAME')
LOCAL_STORAGE_PATH = os.getenv('LOCAL_STORAGE_PATH', 'static/downloads')

# Constants
THUMBNAIL_SIZE = (300, 300)  # Double the previous size

# Initialize Flask app
app = Flask(__name__)
admin = Admin(app, name='Storage Admin', template_mode='bootstrap3')

# Configure logging
logging.basicConfig(level=logging.INFO)

def upload_file_to_cloud(file_path, file_name):
    if CLOUD_STORAGE_PROVIDER == 's3':
        s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
        try:
            s3.upload_file(file_path, BUCKET_NAME, file_name)
            logging.info(f"{file_name} uploaded to S3.")
        except NoCredentialsError:
            logging.error("Credentials not available.")
    elif CLOUD_STORAGE_PROVIDER == 'b2':
        info = b2.InMemoryAccountInfo()
        b2_api = b2.B2Api(info)
        application_key_id = ACCESS_KEY
        application_key = SECRET_KEY
        b2_api.authorize_account("production", application_key_id, application_key)
        bucket = b2_api.get_bucket_by_name(BUCKET_NAME)
        bucket.upload_local_file(local_file=file_path, file_name=file_name)
        logging.info(f"{file_name} uploaded to B2.")

def save_file(file, file_path):
    if USE_CLOUD_STORAGE:
        upload_file_to_cloud(file_path, file.filename)
    else:
        file.save(file_path)
        logging.info(f"{file.filename} saved locally.")

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

def download_images(word):
    """Download images based on the search word and save them to a directory."""
    urls = search(word)
    directory = Path(LOCAL_STORAGE_PATH) / word
    directory.mkdir(exist_ok=True, parents=True)
    for index, url in enumerate(urls, start=1):
        path = str(directory / f'{word}_{index:03}.jpg')
        save_img(url, path)
        logging.info(f"Saved image: {path}")
        create_thumbnail_for_image(path)

@app.route('/progress/<word>', methods=['GET'])
def progress(word):
    """Serve the progress of thumbnails for the given word."""
    directory = Path(LOCAL_STORAGE_PATH) / word / 'thumbnails'
    thumbnails = list(directory.glob('*.webp'))
    thumbnail_urls = [url_for('static', filename=f'downloads/{word}/thumbnails/{thumbnail.name}') for thumbnail in thumbnails]
    html = '<link rel="stylesheet" href="https://startr.style/style.css"><h2 style=""--ta:center; --mb:2rem>Downloading images...</h2>'
    for url in thumbnail_urls:
        html += f'<img src="{url}" alt="thumbnail" style="--br:0.6rem; --shadow:8; --m:1rem">'
        if thumbnail_urls.index(url) % 4 == 3:
            html += '<br>'
    html +='<!-- blinking ... --> <style> @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0; } 100% { opacity: 1; } } .blink { animation: blink 1s infinite; } </style> <span class="blink" style="--m:1rem">...</span>'
    return html

@app.route('/imageset/<word>', methods=['GET'])
def image_set(word):
    """Display images in a set and provide download links."""
    directory = Path(LOCAL_STORAGE_PATH) / word
    if not directory.exists():
        abort(404)
    
    images = list(directory.glob('*.jpg'))
    image_urls = [url_for('static', filename=f'downloads/{word}/{image.name}') for image in images]
    return render_template('imageset.html', word=word, image_urls=image_urls)

@app.route('/download_image/<word>/<filename>', methods=['GET'])
def download_image(word, filename):
    """Serve individual image for download."""
    file_path = Path(LOCAL_STORAGE_PATH) / word / filename
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
        if not thumbnail_path.exists():
            with Image.open(image_path) as img:
                img.thumbnail(THUMBNAIL_SIZE)
                img.save(thumbnail_path, 'WEBP')
                logging.info(f"Created thumbnail: {thumbnail_path}")
        else:
            logging.info(f"Thumbnail already exists: {thumbnail_path}")
    except FileNotFoundError:
        logging.error(f"File not found: {image_path}")
    except Exception as e:
        logging.error(f"Error creating thumbnail for {image_path}: {e}")

def get_prior_searches():
    """Retrieve information about prior searches for display."""
    prior_searches = []
    download_path = Path(LOCAL_STORAGE_PATH)
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

class StorageAdminView(BaseView):
    @expose('/')
    def index(self):
        return self.render('admin/index.html')
    
    @expose('/migrate_to_cloud')
    def migrate_to_cloud(self):
        for root, dirs, files in os.walk(LOCAL_STORAGE_PATH):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                upload_file_to_cloud(file_path, os.path.relpath(file_path, LOCAL_STORAGE_PATH))
        return redirect(url_for('.index'))

    @expose('/migrate_to_local')
    def migrate_to_local(self):
        if CLOUD_STORAGE_PROVIDER == 's3':
            s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
            for file_obj in s3.list_objects_v2(Bucket=BUCKET_NAME).get('Contents', []):
                file_name = file_obj['Key']
                local_path = os.path.join(LOCAL_STORAGE_PATH, file_name)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                s3.download_file(BUCKET_NAME, file_name, local_path)
        elif CLOUD_STORAGE_PROVIDER == 'b2':
            info = b2.InMemoryAccountInfo()
            b2_api = b2.B2Api(info)
            application_key_id = ACCESS_KEY
            application_key = SECRET_KEY
            b2_api.authorize_account("production", application_key_id, application_key)
            bucket = b2_api.get_bucket_by_name(BUCKET_NAME)
            for file_version in bucket.ls():
                file_name = file_version.file_name
                local_path = os.path.join(LOCAL_STORAGE_PATH, file_name)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                bucket.download_file_by_name(file_name, local_path)
        return redirect(url_for('.index'))

admin.add_view(StorageAdminView(name='Manage Storage'))

if __name__ == '__main__':
    # Create thumbnails for existing directories at startup
    download_path = Path(LOCAL_STORAGE_PATH)
    for directory in download_path.iterdir():
        if directory.is_dir():
            create_thumbnail(directory)
    app.run(debug=True)
