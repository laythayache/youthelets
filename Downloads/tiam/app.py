# -*- coding: utf-8 -*-
"""
Flask Face Matching Application
Converts the Colab notebook into a web application with Google Drive integration
"""

import os
import cv2
import shutil
import json
import base64
import numpy as np
import pandas as pd
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, session, make_response
from werkzeug.utils import secure_filename
import torch
from insightface.app import FaceAnalysis
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io
import zipfile
import requests
from functools import wraps
import hashlib
import time

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year cache for static files
# Increase timeout for long-running operations (Windows doesn't support SIGALRM)
import signal
if hasattr(signal, 'SIGALRM'):
    signal.signal(signal.SIGALRM, lambda s, f: None)  # Prevent timeout on long operations

# Image cache - stores processed images in memory
class SimpleImageCache:
    def __init__(self, default_timeout=3600):
        self.cache = {}
        self.default_timeout = default_timeout
        self.timestamps = {}
    
    def get(self, key):
        if key in self.cache:
            # Check if expired
            if time.time() - self.timestamps.get(key, 0) < self.default_timeout:
                return self.cache[key]
            else:
                # Expired, remove it
                del self.cache[key]
                del self.timestamps[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = value
        self.timestamps[key] = time.time()
        # Limit cache size (keep last 1000 items)
        if len(self.cache) > 1000:
            # Remove oldest items
            sorted_items = sorted(self.timestamps.items(), key=lambda x: x[1])
            for old_key, _ in sorted_items[:100]:
                if old_key in self.cache:
                    del self.cache[old_key]
                    del self.timestamps[old_key]

image_cache = SimpleImageCache(default_timeout=3600)  # 1 hour cache
thumbnail_cache_dir = os.path.join(app.config['OUTPUT_FOLDER'], 'thumbnails')
os.makedirs(thumbnail_cache_dir, exist_ok=True)

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Google Drive API configuration
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file']
CLIENT_SECRETS_FILE = 'client_secrets.json'
SERVICE_ACCOUNT_FILE = os.environ.get('SERVICE_ACCOUNT_FILE', 'service_account.json')  # For youtheletes drive

# Load configuration from config.json if it exists, otherwise use environment variables
CONFIG_FILE = 'config.json'
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            YOUTHELETES_DRIVE_FOLDER_ID = config.get('youtheletes_drive_folder_id', '')
    except:
        YOUTHELETES_DRIVE_FOLDER_ID = os.environ.get('YOUTHELETES_DRIVE_FOLDER_ID', '')
else:
    YOUTHELETES_DRIVE_FOLDER_ID = os.environ.get('YOUTHELETES_DRIVE_FOLDER_ID', '')

# Initialize InsightFace (allow server to start even if this fails)
print("Loading InsightFace model...")
face_app = None
insightface_error = None

try:
    # Try newer API (0.7.3+) with providers
    face_app = FaceAnalysis("buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    print("Using InsightFace 0.7.3+ API")
    ctx = 0 if torch.cuda.is_available() else -1
    face_app.prepare(ctx_id=ctx, det_size=(640, 640))
    try:
        device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU ONLY'
    except:
        device_name = 'CPU ONLY'
    print(f"Running on: {device_name}")
except TypeError:
    # Fallback to older API (0.2.1) - uses (name, root) signature
    print("Using InsightFace 0.2.1 API - model will be downloaded if needed...")
    try:
        # Try to initialize - it will download model automatically if not present
        face_app = FaceAnalysis("buffalo_l", root='~/.insightface/models')
        print("Model initialized successfully")
        ctx = 0 if torch.cuda.is_available() else -1
        face_app.prepare(ctx_id=ctx, det_size=(640, 640))
        try:
            device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU ONLY'
        except:
            device_name = 'CPU ONLY'
        print(f"Running on: {device_name}")
    except Exception as e:
        insightface_error = str(e)
        print(f"ERROR: Could not initialize InsightFace: {e}")
        print("\n" + "="*60)
        print("INSIGHTFACE SETUP REQUIRED")
        print("="*60)
        print("The application requires InsightFace 0.7.3 with models.")
        print("Current version: 0.2.1 (incompatible)")
        print("\nTo fix this:")
        print("1. Install Microsoft C++ Build Tools:")
        print("   https://visualstudio.microsoft.com/visual-cpp-build-tools/")
        print("2. Then run: pip uninstall insightface && pip install insightface==0.7.3")
        print("\nThe web server will start, but face matching features will be disabled.")
        print("="*60 + "\n")
except Exception as e:
    insightface_error = str(e)
    print(f"ERROR: Failed to initialize InsightFace: {e}")
    print("Server will start but face matching will be disabled.")

# Global state
VALID_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SIM_THRESHOLD = 0.35
BATCH = 128
PAGE_SIZE = 20

# Store reference embedding in session
ref_embeddings = {}

def load_bgr(path):
    """Load image in BGR format"""
    try:
        with open(path, 'rb') as f:
            arr = np.frombuffer(f.read(), np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except:
        return None

def resize_max(img, max_dim=1280):
    """Resize image maintaining aspect ratio"""
    h, w = img.shape[:2]
    if max(h, w) <= max_dim:
        return img
    s = max_dim / max(h, w)
    return cv2.resize(img, (int(w * s), int(h * s)))

def get_faces(img):
    """Extract faces from image"""
    if face_app is None:
        raise RuntimeError("InsightFace is not initialized. Please install InsightFace 0.7.3. See GUIDE.md for instructions.")
    faces = []
    for f in face_app.get(img):
        faces.append({
            "bbox": f.bbox.astype(int),
            "embedding": f.normed_embedding.astype(np.float32),
            "score": float(f.det_score)
        })
    return faces

def cosine(a, b):
    """Calculate cosine similarity between two embeddings"""
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return float(np.dot(a, b))

def scan_images(folder):
    """Scan folder for images"""
    imgs = []
    if os.path.exists(folder):
        for r, _, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() in VALID_EXT:
                    imgs.append(os.path.join(r, f))
    return sorted(imgs)

def requires_auth(f):
    """Decorator to require Google Drive authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'credentials' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Home page"""
    # Check if auto-load is configured
    auto_load_enabled = bool(YOUTHELETES_DRIVE_FOLDER_ID and os.path.exists(SERVICE_ACCOUNT_FILE))
    return render_template('index.html', 
                         insightface_available=face_app is not None, 
                         insightface_error=insightface_error,
                         auto_load_enabled=auto_load_enabled,
                         drive_folder_id=YOUTHELETES_DRIVE_FOLDER_ID if auto_load_enabled else '')

@app.route('/favicon.ico')
def favicon():
    """Return favicon"""
    return '', 204  # No content

@app.route('/auth')
def auth():
    """Initiate Google Drive OAuth flow"""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return jsonify({
            'error': 'Google Drive credentials not configured',
            'message': 'Please create client_secrets.json file. See README.md for setup instructions.',
            'setup_required': True
        }), 400
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=request.url_root + 'auth/callback'
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return jsonify({'auth_url': authorization_url})

@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback"""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=request.url_root + 'auth/callback',
        state=session['state']
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    return render_template('auth_success.html')

def get_youtheletes_service():
    """Get Google Drive service for youtheletes using service account"""
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        try:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            print(f"Service account error: {e}")
            return None
    return None

def find_folder_by_name(service, parent_folder_id, folder_name):
    """Find a folder by name within a parent folder"""
    try:
        # Search for folders with the exact name
        query = f"'{parent_folder_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name)"
        ).execute()
        
        folders = results.get('files', [])
        if folders:
            return folders[0]['id']  # Return first match
        
        # Try case-insensitive search
        query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name)"
        ).execute()
        
        folders = results.get('files', [])
        for folder in folders:
            if folder_name.lower() in folder['name'].lower():
                return folder['id']
        
        return None
    except Exception as e:
        print(f"Error finding folder: {e}")
        return None

@app.route('/api/drive/folders', methods=['POST'])
def list_drive_folders():
    """List folders from Google Drive - automatically finds event_photos and athlete reference folders"""
    import time
    start_time = time.time()
    
    try:
        # Set a longer timeout for this operation
        import socket
        socket.setdefaulttimeout(300)  # 5 minutes timeout
        data = request.json or {}
        use_youtheletes = data.get('use_youtheletes', False)
        auto_load = data.get('auto_load', False)
        
        # If auto-load is requested, automatically use youtheletes drive
        if auto_load:
            use_youtheletes = True
        
        images = []
        service = None
        
        # If using youtheletes drive, try service account first
        if use_youtheletes and YOUTHELETES_DRIVE_FOLDER_ID:
            service = get_youtheletes_service()
            if not service:
                # Service account not found - provide clear instructions
                error_msg = (
                    'Service account not configured. To allow parents to access photos without authentication:\n\n'
                    '1. Go to Google Cloud Console (https://console.cloud.google.com/)\n'
                    '2. Create/select your project and enable Google Drive API\n'
                    '3. Create a Service Account (Credentials → Service Account)\n'
                    '4. Download the JSON key file and save as "service_account.json"\n'
                    '5. Share your Drive folder with the service account email\n'
                    '   (Right-click folder → Share → Add service account email → Viewer access)\n\n'
                    'See GUIDE.md for detailed instructions.'
                )
                return jsonify({
                    'error': 'Service account setup required',
                    'message': error_msg,
                    'setup_required': True
                }), 400
            
            # Automatically find folders by name
            root_folder_id = YOUTHELETES_DRIVE_FOLDER_ID
            
            # Automatically find folders by name (searches recursively in subfolders too)
            # Find event photos folder (try multiple name variations)
            event_folder_names = ['event_photos_inout', 'event_photos_input', 'event_photos', 'Event_Photos_Input', 'Event_Photos_Inout']
            event_folder_id = None
            for name in event_folder_names:
                event_folder_id = find_folder_by_name(service, root_folder_id, name)
                if event_folder_id:
                    print(f"✅ Found event photos folder: {name} (ID: {event_folder_id})")
                    break
            
            # Find athlete reference folder (try multiple name variations)
            athlete_folder_names = ['Athlete_101_Reference', 'Athlete_Reference', 'athlete_reference', 'Reference', 'Athlete_101']
            athlete_folder_id = None
            for name in athlete_folder_names:
                athlete_folder_id = find_folder_by_name(service, root_folder_id, name)
                if athlete_folder_id:
                    print(f"✅ Found athlete reference folder: {name} (ID: {athlete_folder_id})")
                    break
            
            if not event_folder_id:
                return jsonify({
                    'error': 'Could not find event photos folder',
                    'message': f'Looking for folders named: {", ".join(event_folder_names)}\nPlease ensure these folders exist in your Drive root folder.'
                }), 404
            
            folder1_id = athlete_folder_id if athlete_folder_id else ''
            folder2_id = event_folder_id
        elif use_youtheletes and not YOUTHELETES_DRIVE_FOLDER_ID:
            return jsonify({'error': 'youtheletes drive folder ID not configured. Please set YOUTHELETES_DRIVE_FOLDER_ID environment variable.'}), 400
        else:
            # User's own drive - requires authentication
            if 'credentials' not in session:
                return jsonify({'error': 'Please authenticate Google Drive first'}), 401
            creds = Credentials(**session['credentials'])
            service = build('drive', 'v3', credentials=creds)
        
        download_count = [0]  # Use list to allow modification in nested function
        
        def download_folder_recursive(folder_id, local_path, max_depth=5, current_depth=0):
            """Recursively download images from folder and all subfolders"""
            if current_depth >= max_depth:
                return []
            
            os.makedirs(local_path, exist_ok=True)
            all_images = []
            
            try:
                # Get all files and folders in this directory
                results = service.files().list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    fields="files(id, name, mimeType)",
                    pageSize=1000
                ).execute()
                
                items = results.get('files', [])
                
                for item in items:
                    # If it's an image, download it
                    if 'image/' in item.get('mimeType', ''):
                        try:
                            request_download = service.files().get_media(fileId=item['id'])
                            file_path = os.path.join(local_path, item['name'])
                            with open(file_path, 'wb') as f:
                                downloader = MediaIoBaseDownload(f, request_download)
                                done = False
                                while not done:
                                    status, done = downloader.next_chunk()
                            all_images.append(file_path)
                            download_count[0] += 1
                            if download_count[0] % 100 == 0:
                                print(f"Downloaded {download_count[0]} images...")
                        except Exception as e:
                            print(f"Error downloading {item['name']}: {e}")
                    
                    # If it's a folder, recurse into it
                    elif item.get('mimeType') == 'application/vnd.google-apps.folder':
                        subfolder_path = os.path.join(local_path, item['name'])
                        sub_images = download_folder_recursive(
                            item['id'], 
                            subfolder_path, 
                            max_depth, 
                            current_depth + 1
                        )
                        all_images.extend(sub_images)
            except Exception as e:
                print(f"Error accessing folder {folder_id}: {e}")
                return all_images
            
            return all_images
        
        def download_folder(folder_id, local_path):
            """Download all images from folder (including subfolders)"""
            images = download_folder_recursive(folder_id, local_path)
            # Also scan the local path for any images that might have been downloaded
            scanned = scan_images(local_path)
            # Combine and deduplicate
            all_images = list(set(images + scanned))
            return sorted(all_images)
        
        folder1_path = os.path.join(app.config['UPLOAD_FOLDER'], 'folder1')
        folder2_path = os.path.join(app.config['UPLOAD_FOLDER'], 'folder2')
        
        if folder1_id:
            print(f"Downloading from athlete reference folder...")
            images.extend(download_folder(folder1_id, folder1_path))
        if folder2_id:
            print(f"Downloading from event photos folder...")
            images.extend(download_folder(folder2_id, folder2_path))
        
        elapsed_time = time.time() - start_time
        print(f"✅ Total download time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
        print(f"✅ Total images loaded: {len(images)}")
        
        return jsonify({
            'images': images, 
            'count': len(images),
            'download_time': round(elapsed_time, 1),
            'download_time_minutes': round(elapsed_time/60, 1)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/images/scan', methods=['POST'])
def scan_local_folders():
    """Scan local folders for images"""
    try:
        data = request.json
        folder1 = data.get('folder1', '')
        folder2 = data.get('folder2', '')
        
        images = []
        if folder1:
            images.extend(scan_images(folder1))
        if folder2:
            images.extend(scan_images(folder2))
        
        return jsonify({'images': images, 'count': len(images)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_thumbnail_path(img_path):
    """Get cached thumbnail file path"""
    path_hash = hashlib.md5(img_path.encode()).hexdigest()
    return os.path.join(thumbnail_cache_dir, f"{path_hash}.jpg")

def get_or_create_thumbnail(img_path, max_size=256):
    """Get thumbnail from cache or create it"""
    # Check memory cache first
    cache_key = f"thumb_{img_path}_{max_size}"
    cached = image_cache.get(cache_key)
    if cached is not None:
        return cached
    
    # Check disk cache
    thumb_path = get_thumbnail_path(img_path)
    if os.path.exists(thumb_path):
        with open(thumb_path, 'rb') as f:
            thumb_data = f.read()
        image_cache.set(cache_key, thumb_data)
        return thumb_data
    
    # Generate thumbnail
    img = load_bgr(img_path)
    if img is None:
        return None
    
    thumb = resize_max(img, max_size)
    ok, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return None
    
    thumb_data = buf.tobytes()
    
    # Save to disk cache
    try:
        with open(thumb_path, 'wb') as f:
            f.write(thumb_data)
    except:
        pass  # Ignore disk write errors
    
    # Cache in memory
    image_cache.set(cache_key, thumb_data)
    return thumb_data

@app.route('/api/gallery', methods=['POST'])
def get_gallery():
    """Get paginated gallery of images"""
    try:
        data = request.json
        images = data.get('images', [])
        page = int(data.get('page', 1))
        
        start = (page - 1) * PAGE_SIZE
        end = min(len(images), start + PAGE_SIZE)
        page_images = images[start:end]
        
        # Generate thumbnails with caching
        thumbnails = []
        for img_path in page_images:
            thumb_data = get_or_create_thumbnail(img_path, 256)
            if thumb_data is None:
                continue
            
            img_base64 = base64.b64encode(thumb_data).decode('utf-8')
            
            thumbnails.append({
                'path': img_path,
                'thumbnail': f'data:image/jpeg;base64,{img_base64}',
                'index': images.index(img_path)
            })
        
        return jsonify({
            'thumbnails': thumbnails,
            'page': page,
            'total_pages': (len(images) + PAGE_SIZE - 1) // PAGE_SIZE,
            'total': len(images)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/image/load', methods=['POST'])
def load_image():
    """Load full image and detect faces automatically"""
    try:
        data = request.json
        img_path = data.get('path', '')
        
        img = load_bgr(img_path)
        if img is None:
            return jsonify({'error': 'Could not load image'}), 400
        
        img_resized = resize_max(img, 1024)
        h, w = img_resized.shape[:2]
        
        # Detect all faces in the image
        faces = get_faces(img_resized)
        
        # Draw bounding boxes on image for visualization
        img_with_boxes = img_resized.copy()
        face_data = []
        
        for i, face in enumerate(faces):
            bbox = face['bbox']  # [x1, y1, x2, y2]
            score = face['score']
            
            # Draw bounding box
            cv2.rectangle(img_with_boxes, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
            # Add face number label
            cv2.putText(img_with_boxes, f'Face {i+1}', (bbox[0], bbox[1] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Extract face thumbnail
            face_crop = img_resized[max(0, bbox[1]):min(h, bbox[3]), max(0, bbox[0]):min(w, bbox[2])]
            if face_crop.size > 0:
                ok, face_buf = cv2.imencode(".jpg", face_crop)
                face_base64 = base64.b64encode(face_buf).decode('utf-8')
            else:
                face_base64 = None
            
            face_data.append({
                'index': i,
                'bbox': bbox.tolist(),
                'score': score,
                'thumbnail': f'data:image/jpeg;base64,{face_base64}' if face_base64 else None
            })
        
        # Encode image with boxes
        ok, buf = cv2.imencode(".jpg", img_with_boxes)
        img_base64 = base64.b64encode(buf).decode('utf-8')
        
        return jsonify({
            'image': f'data:image/jpeg;base64,{img_base64}',
            'width': w,
            'height': h,
            'faces': face_data,
            'face_count': len(faces)
        })
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in load_image: {error_trace}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/face/set', methods=['POST'])
def set_reference_face():
    """Set reference face from detected face index"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        img_path = data.get('path', '')
        if not img_path:
            return jsonify({'error': 'No image path provided'}), 400
        
        face_index = data.get('face_index', None)
        if face_index is None:
            return jsonify({'error': 'No face index provided'}), 400
        
        try:
            face_index = int(face_index)
        except (ValueError, TypeError) as e:
            return jsonify({'error': f'Invalid face index: {e}'}), 400
        
        img = load_bgr(img_path)
        if img is None:
            return jsonify({'error': f'Could not load image from path: {img_path}'}), 400
        
        img_resized = resize_max(img, 1024)
        
        # Detect faces again to get embeddings
        faces = get_faces(img_resized)
        
        if not faces:
            return jsonify({'error': 'No faces detected in image'}), 400
        
        if face_index < 0 or face_index >= len(faces):
            return jsonify({'error': f'Invalid face index: {face_index}. Found {len(faces)} faces.'}), 400
        
        # Get the selected face's embedding
        selected_face = faces[face_index]
        emb = selected_face["embedding"]
        ref_embedding = emb / (np.linalg.norm(emb) + 1e-9)
        
        # Store in session
        session_id = session.get('session_id', os.urandom(16).hex())
        session['session_id'] = session_id
        ref_embeddings[session_id] = ref_embedding
        
        return jsonify({
            'success': True,
            'message': f'Reference face {face_index + 1} set successfully',
            'session_id': session_id,
            'face_index': face_index
        })
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in set_reference_face: {error_trace}")
        return jsonify({'error': str(e), 'traceback': error_trace}), 500

@app.route('/api/match/run', methods=['POST'])
def run_matching():
    """Run face matching against all images"""
    try:
        data = request.json
        images = data.get('images', [])
        session_id = session.get('session_id')
        
        if not session_id or session_id not in ref_embeddings:
            return jsonify({'error': 'No reference face set'}), 400
        
        ref_embedding = ref_embeddings[session_id]
        results = []
        
        for img_path in images:
            img = load_bgr(img_path)
            if img is None:
                results.append({
                    "image_path": img_path,
                    "max_similarity": 0,
                    "faces": 0
                })
                continue
            
            faces = get_faces(resize_max(img))
            if not faces:
                results.append({
                    "image_path": img_path,
                    "max_similarity": 0,
                    "faces": 0
                })
                continue
            
            sims = [cosine(ref_embedding, f["embedding"]) for f in faces]
            results.append({
                "image_path": img_path,
                "max_similarity": max(sims) if sims else 0,
                "faces": len(faces)
            })
        
        df = pd.DataFrame(results)
        df["is_match"] = (df["max_similarity"] >= SIM_THRESHOLD).astype(int)
        
        # Save CSV
        csv_path = os.path.join(app.config['OUTPUT_FOLDER'], 'matches.csv')
        df.to_csv(csv_path, index=False)
        
        return jsonify({
            'success': True,
            'matched': int(df['is_match'].sum()),
            'total': len(df),
            'results': df.to_dict('records')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export', methods=['POST'])
def export_matches():
    """Export matched images to folder"""
    try:
        data = request.json
        folder_name = data.get('folder_name', 'matched_photos')
        results = data.get('results', [])
        
        csv_path = os.path.join(app.config['OUTPUT_FOLDER'], 'matches.csv')
        if not os.path.exists(csv_path):
            return jsonify({'error': 'No matches found. Run matching first.'}), 400
        
        df = pd.read_csv(csv_path)
        matches = df[df["is_match"] == 1]
        
        outdir = os.path.join(app.config['OUTPUT_FOLDER'], secure_filename(folder_name))
        os.makedirs(outdir, exist_ok=True)
        
        exported = []
        for _, row in matches.iterrows():
            src = row["image_path"]
            if not os.path.exists(src):
                continue
            
            fname = Path(src).name
            dst = os.path.join(outdir, fname)
            
            if os.path.exists(dst):
                stem, ext = os.path.splitext(fname)
                i = 1
                while True:
                    new = f"{stem}_{i}{ext}"
                    if not os.path.exists(os.path.join(outdir, new)):
                        dst = os.path.join(outdir, new)
                        break
                    i += 1
            
            shutil.copy2(src, dst)
            exported.append(dst)
        
        return jsonify({
            'success': True,
            'exported': len(exported),
            'folder': outdir
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/zip', methods=['POST'])
def export_zip():
    """Export matched images as ZIP file"""
    try:
        data = request.json
        zip_name = data.get('zip_name', 'matched_photos.zip')
        
        csv_path = os.path.join(app.config['OUTPUT_FOLDER'], 'matches.csv')
        if not os.path.exists(csv_path):
            return jsonify({'error': 'No matches found. Run matching first.'}), 400
        
        df = pd.read_csv(csv_path)
        matches = df[df["is_match"] == 1]
        
        if len(matches) == 0:
            return jsonify({'error': 'No matched photos to export'}), 400
        
        zip_path = os.path.join(app.config['OUTPUT_FOLDER'], secure_filename(zip_name))
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for _, row in matches.iterrows():
                src = row["image_path"]
                if os.path.exists(src):
                    zipf.write(src, Path(src).name)
        
        return send_file(zip_path, as_attachment=True, download_name=zip_name)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/drive', methods=['POST'])
@requires_auth
def export_to_drive():
    """Send matched images to user's Google Drive"""
    try:
        data = request.json
        folder_name = data.get('folder_name', 'Matched Photos')
        
        csv_path = os.path.join(app.config['OUTPUT_FOLDER'], 'matches.csv')
        if not os.path.exists(csv_path):
            return jsonify({'error': 'No matches found. Run matching first.'}), 400
        
        df = pd.read_csv(csv_path)
        matches = df[df["is_match"] == 1]
        
        if len(matches) == 0:
            return jsonify({'error': 'No matched photos to export'}), 400
        
        creds = Credentials(**session['credentials'])
        service = build('drive', 'v3', credentials=creds)
        
        # Create folder in user's drive
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')
        
        uploaded = []
        for _, row in matches.iterrows():
            src = row["image_path"]
            if not os.path.exists(src):
                continue
            
            file_metadata = {
                'name': Path(src).name,
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(src, resumable=True)
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name'
            ).execute()
            uploaded.append(file.get('name'))
        
        return jsonify({
            'success': True,
            'uploaded': len(uploaded),
            'folder_id': folder_id,
            'folder_name': folder_name,
            'files': uploaded
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/results')
def get_results():
    """Get matching results"""
    try:
        csv_path = os.path.join(app.config['OUTPUT_FOLDER'], 'matches.csv')
        if not os.path.exists(csv_path):
            return jsonify({'error': 'No results found'}), 404
        
        df = pd.read_csv(csv_path)
        return jsonify({
            'results': df.to_dict('records'),
            'matched': int(df['is_match'].sum()),
            'total': len(df)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/image')
def serve_image():
    """Serve image files with caching"""
    try:
        image_path = request.args.get('path', '')
        max_size = int(request.args.get('size', 800))
        
        if not image_path:
            return jsonify({'error': 'No path provided'}), 400
        
        # Decode the path (handle URL encoding)
        import urllib.parse
        image_path = urllib.parse.unquote(image_path)
        
        # Check cache
        cache_key = f"img_{image_path}_{max_size}"
        cached = image_cache.get(cache_key)
        if cached is not None:
            response = make_response(cached)
            response.headers['Content-Type'] = 'image/jpeg'
            response.headers['Cache-Control'] = 'public, max-age=3600'  # 1 hour browser cache
            response.headers['ETag'] = hashlib.md5(cached).hexdigest()
            return response
        
        # Normalize path separators
        if os.path.exists(image_path) and os.path.splitext(image_path)[1].lower() in VALID_EXT:
            img = load_bgr(image_path)
            if img is not None:
                resized = resize_max(img, max_size)
                ok, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ok:
                    img_bytes = buf.tobytes()
                    # Cache the result
                    image_cache.set(cache_key, img_bytes)
                    
                    response = make_response(img_bytes)
                    response.headers['Content-Type'] = 'image/jpeg'
                    response.headers['Cache-Control'] = 'public, max-age=3600'  # 1 hour browser cache
                    response.headers['ETag'] = hashlib.md5(img_bytes).hexdigest()
                    return response
        
        return jsonify({'error': 'Image not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

