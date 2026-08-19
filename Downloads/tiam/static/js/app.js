// Global state
let allImages = [];
let currentPage = 1;
let totalPages = 1;
let currentImagePath = null;
let cropData = { x1: 0, y1: 0, x2: 0, y2: 0 };
let isCropping = false;
let cropStart = { x: 0, y: 0 };
let cropEnd = { x: 0, y: 0 };
let matchingResults = [];

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    handleDriveReturn();

    // Auto-load if configured
    if (typeof autoLoadEnabled !== 'undefined' && autoLoadEnabled) {
        autoLoadFromDrive();
    }
});

// Google sends the visitor back to /?drive=... in the same tab they left from,
// so pick that up and drop them straight into the Drive step rather than on a
// page telling them to close a window they never opened.
function handleDriveReturn() {
    const params = new URLSearchParams(window.location.search);
    const outcome = params.get('drive');
    const connected = (typeof driveConnected !== 'undefined' && driveConnected);

    if (outcome === 'failed') {
        selectSource('drive');
        showAuthStatus('Google sign-in did not complete. You can try again, or use Upload Photos instead.', 'error');
    } else if (outcome === 'connected' || connected) {
        selectSource('drive');
        showAuthStatus('Connected to Google Drive.', 'success');
    }

    if (outcome) {
        // do not leave the marker in the address bar, or a refresh replays it
        window.history.replaceState({}, '', window.location.pathname);
    }
}

async function autoLoadFromDrive() {
    // Hide folder selection UI
    const step1 = document.getElementById('step1');
    if (step1) {
        step1.style.display = 'none';
    }
    
    // Show loading message
    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'card';
    loadingMsg.id = 'auto-loading';
    loadingMsg.innerHTML = `
        <h2>🔄 Loading Images from Google Drive...</h2>
        <p>Please wait while we load images from your Drive folder.</p>
        <div class="progress-bar">
            <div class="progress-fill" style="width: 30%;"></div>
        </div>
    `;
    document.querySelector('.main-content').insertBefore(loadingMsg, step1);
    
    try {
        // Call the auto-load endpoint
        const response = await fetch('/api/drive/folders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                use_youtheletes: true,
                auto_load: true
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            allImages = data.images;
            document.getElementById('total-images-count').textContent = allImages.length;
            
            // Remove loading message
            loadingMsg.remove();
            
            // Show success and go to gallery
            showStep(2);
            loadGallery(1);
        } else {
            loadingMsg.innerHTML = `
                <h2>❌ Error Loading Images</h2>
                <p style="color: #dc2626;">${data.error || data.message || 'Unknown error'}</p>
                <button class="btn btn-primary" onclick="location.reload()">Retry</button>
            `;
        }
    } catch (error) {
        loadingMsg.innerHTML = `
            <h2>❌ Connection Error</h2>
            <p style="color: #dc2626;">${error.message}</p>
            <button class="btn btn-primary" onclick="location.reload()">Retry</button>
        `;
    }
}

function setupEventListeners() {
    // Source selection
    document.getElementById('local-option').addEventListener('click', () => {
        selectSource('local');
    });
    
    document.getElementById('drive-option').addEventListener('click', () => {
        selectSource('drive');
    });
}

function selectSource(source) {
    // Remove previous selections
    document.querySelectorAll('.option-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Hide all input sections
    document.getElementById('local-input').style.display = 'none';
    document.getElementById('drive-input').style.display = 'none';
    
    // Show selected option
    if (source === 'local') {
        document.getElementById('local-option').classList.add('selected');
        document.getElementById('local-input').style.display = 'block';
    } else {
        document.getElementById('drive-option').classList.add('selected');
        document.getElementById('drive-input').style.display = 'block';
    }
}

async function uploadPhotos() {
    const input = document.getElementById('photo-files');
    const status = document.getElementById('upload-status');
    const files = input.files;

    if (!files || files.length === 0) {
        alert('Please choose some photos first');
        return;
    }

    const form = new FormData();
    for (const f of files) {
        form.append('files', f);
    }

    status.textContent = `Uploading ${files.length} photo(s)...`;

    try {
        const response = await fetch('/api/images/upload', {
            method: 'POST',
            body: form
        });

        const data = await response.json();

        if (response.ok) {
            if (data.count === 0) {
                status.textContent = 'None of those files were usable images.';
                return;
            }
            // skipped covers non-images the picker let through, e.g. HEIC or video
            status.textContent = data.skipped
                ? `Uploaded ${data.count}, skipped ${data.skipped} unsupported file(s).`
                : `Uploaded ${data.count} photo(s).`;
            allImages = data.images;
            document.getElementById('total-images-count').textContent = allImages.length;
            showStep(2);
            loadGallery(1);
        } else {
            status.textContent = '';
            alert('Error: ' + data.error);
        }
    } catch (error) {
        status.textContent = '';
        alert('Error uploading photos: ' + error.message);
    }
}

async function authenticateDrive() {
    try {
        const response = await fetch('/auth');
        const data = await response.json();
        
        if (data.auth_url) {
            window.location.href = data.auth_url;
            return;
        }
        // the server distinguishes "nobody has configured Google yet" from a real
        // failure; saying which one saves the visitor guessing at a dead end
        if (data.setup_required) {
            showAuthStatus(
                'Google Drive is not set up on this server yet, so there is nothing to sign in to. '
                + 'Use "Upload Photos" instead - it works without a Google account.',
                'error');
            return;
        }
        showAuthStatus(data.error || data.message || ('Could not start Google sign-in (HTTP ' + response.status + ')'), 'error');
    } catch (error) {
        showAuthStatus('Error: ' + error.message, 'error');
    }
}

function showAuthStatus(message, type) {
    const statusDiv = document.getElementById('auth-status');
    statusDiv.textContent = message;
    statusDiv.className = type === 'success' ? 'auth-success-msg' : 'auth-error-msg';
    if (type === 'success') {
        document.getElementById('drive-browser').style.display = 'block';
    }
}

// --- Google Drive, via Google's own Picker --------------------------------
// The app holds the drive.file scope, which grants access only to what the
// visitor hands over in the Picker. That is why there is no folder browser
// here: listing someone's Drive is not something this scope can do.
// Anything that goes wrong in the browser is invisible from the server, which is
// why "nothing happened" was so hard to chase. Ship it back to the log instead.
function clientLog(where, message) {
    try {
        fetch('/api/client-log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ where: where, message: String(message) })
        });
    } catch (e) { /* logging must never break the page */ }
}

window.addEventListener('error', e => {
    clientLog('window.error', (e.message || '?') + ' @ ' + (e.filename || '?') + ':' + (e.lineno || 0));
});
window.addEventListener('unhandledrejection', e => {
    clientLog('unhandled', (e.reason && e.reason.message) || String(e.reason));
});

let pickerApiLoaded = false;

// api.js is loaded async, so gapi is usually NOT there yet when someone clicks.
// Waiting for it is the difference between working and "Google could not be reached".
function waitForGapi(timeoutMs) {
    return new Promise((resolve, reject) => {
        const started = Date.now();
        (function poll() {
            if (typeof gapi !== 'undefined') return resolve();
            if (Date.now() - started > timeoutMs) {
                return reject(new Error('Google\'s picker library did not load. An ad blocker or network filter may be blocking apis.google.com.'));
            }
            setTimeout(poll, 100);
        })();
    });
}

async function loadPickerApi() {
    if (pickerApiLoaded) return;
    await waitForGapi(10000);
    await new Promise((resolve, reject) => {
        gapi.load('picker', {
            callback: () => { pickerApiLoaded = true; resolve(); },
            onerror: () => reject(new Error('Google Picker failed to load.')),
            timeout: 10000,
            ontimeout: () => reject(new Error('Google Picker timed out loading.'))
        });
    });
}

async function openDrivePicker() {
    const status = document.getElementById('drive-import-status');
    status.textContent = 'Opening Google Drive…';
    clientLog('picker', 'open clicked');

    let cfg;
    try {
        const response = await fetch('/api/drive/picker-config');
        cfg = await response.json();
        if (!response.ok) {
            status.textContent = '';
            clientLog('picker', 'config ' + response.status + ' ' + (cfg.error || ''));
            if (cfg.auth_required) {
                showAuthStatus('Your Google session expired. Connect again.', 'error');
                document.getElementById('drive-browser').style.display = 'none';
            } else {
                showAuthStatus(cfg.error || 'Could not open Google Drive', 'error');
            }
            return;
        }
    } catch (error) {
        status.textContent = '';
        clientLog('picker', 'config fetch failed: ' + error.message);
        alert('Could not reach the server: ' + error.message);
        return;
    }

    try {
        await loadPickerApi();
    } catch (error) {
        status.textContent = '';
        clientLog('picker', 'library: ' + error.message);
        alert(error.message);
        return;
    }

    try {
        const photos = new google.picker.DocsView(google.picker.ViewId.DOCS_IMAGES)
            .setIncludeFolders(true)
            .setSelectFolderEnabled(true);

        const picker = new google.picker.PickerBuilder()
            .setTitle('Choose the photos to search')
            .setOAuthToken(cfg.access_token)
            .setDeveloperKey(cfg.api_key)
            .setAppId(cfg.app_id)
            .addView(photos)
            .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
            .setCallback(pickerCallback)
            .build();

        status.textContent = '';
        picker.setVisible(true);
        clientLog('picker', 'opened');
    } catch (error) {
        status.textContent = '';
        clientLog('picker', 'build failed: ' + error.message);
        alert('Google Picker could not start: ' + error.message);
    }
}

async function pickerCallback(data) {
    clientLog('picker', 'callback action=' + data.action);
    if (data.action !== google.picker.Action.PICKED) {
        return;
    }

    const fileIds = [];
    const folderIds = [];
    data.docs.forEach(doc => {
        if (doc.mimeType === 'application/vnd.google-apps.folder') folderIds.push(doc.id);
        else fileIds.push(doc.id);
    });
    clientLog('picker', 'picked ' + fileIds.length + ' file(s), ' + folderIds.length + ' folder(s)');

    const status = document.getElementById('drive-import-status');
    status.textContent = 'Copying ' + (fileIds.length + folderIds.length)
        + ' item(s) from Google Drive — a whole folder can take a while.';

    try {
        const response = await fetch('/api/drive/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_ids: fileIds, folder_ids: folderIds })
        });
        const result = await response.json();
        if (!response.ok) {
            status.textContent = '';
            clientLog('picker', 'import failed ' + response.status + ' ' + (result.error || ''));
            alert('Error: ' + result.error);
            return;
        }

        if (result.count === 0) {
            status.textContent = result.unreadable_folders
                ? 'Google did not grant access to that folder. Open the folder in the picker and select the photos themselves.'
                : 'No usable photos were found in that selection.';
            return;
        }

        status.textContent = 'Imported ' + result.count + ' photo(s).'
            + (result.unreadable_folders
                ? ' ' + result.unreadable_folders + ' folder(s) could not be opened — select the photos inside them instead.'
                : '');

        allImages = result.images;
        document.getElementById('total-images-count').textContent = allImages.length;
        showStep(2);
        loadGallery(1);
    } catch (error) {
        status.textContent = '';
        clientLog('picker', 'import threw: ' + error.message);
        alert('Error importing: ' + error.message);
    }
}

async function loadGallery(page) {
    try {
        const response = await fetch('/api/gallery', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ images: allImages, page })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentPage = data.page;
            totalPages = data.total_pages;
            
            document.getElementById('page-info').textContent = 
                `Page ${currentPage} / ${totalPages}`;
            
            const gallery = document.getElementById('image-gallery');
            gallery.innerHTML = '';
            
            data.thumbnails.forEach(item => {
                const div = document.createElement('div');
                div.className = 'gallery-item';
                div.innerHTML = `
                    <img src="${item.thumbnail}" alt="Image ${item.index + 1}">
                    <div class="item-label">Image #${item.index + 1}</div>
                `;
                div.addEventListener('click', () => openCropUI(item.path));
                gallery.appendChild(div);
            });
        } else {
            alert('Error loading gallery: ' + data.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function prevPage() {
    if (currentPage > 1) {
        loadGallery(currentPage - 1);
    }
}

function nextPage() {
    if (currentPage < totalPages) {
        loadGallery(currentPage + 1);
    }
}

async function openCropUI(imagePath) {
    currentImagePath = imagePath;
    
    try {
        const response = await fetch('/api/image/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: imagePath })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            const img = document.getElementById('crop-image');
            img.src = data.image;
            img.onload = function() {
                setupCropCanvas(data.width, data.height);
                showStep(3);
            };
        } else {
            alert('Error loading image: ' + data.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function setupCropCanvas(width, height) {
    const canvas = document.getElementById('crop-canvas');
    const img = document.getElementById('crop-image');
    
    // Wait for image to load
    img.onload = function() {
        canvas.width = img.offsetWidth;
        canvas.height = img.offsetHeight;
        
        const ctx = canvas.getContext('2d');
        const scaleX = img.naturalWidth / img.offsetWidth;
        const scaleY = img.naturalHeight / img.offsetHeight;
        
        // Initialize crop area to center
        cropData = {
            x1: Math.floor(width / 4),
            y1: Math.floor(height / 4),
            x2: Math.floor(width * 3 / 4),
            y2: Math.floor(height * 3 / 4)
        };
        
        canvas.addEventListener('mousedown', (e) => {
            isCropping = true;
            const rect = canvas.getBoundingClientRect();
            cropStart = {
                x: (e.clientX - rect.left) * scaleX,
                y: (e.clientY - rect.top) * scaleY
            };
        });
        
        canvas.addEventListener('mousemove', (e) => {
            if (isCropping) {
                const rect = canvas.getBoundingClientRect();
                cropEnd = {
                    x: (e.clientX - rect.left) * scaleX,
                    y: (e.clientY - rect.top) * scaleY
                };
                drawCropBox(ctx, cropStart, cropEnd, scaleX, scaleY, img.offsetWidth, img.offsetHeight);
            }
        });
        
        canvas.addEventListener('mouseup', () => {
            if (isCropping) {
                isCropping = false;
                cropData = {
                    x1: Math.floor(Math.min(cropStart.x, cropEnd.x)),
                    y1: Math.floor(Math.min(cropStart.y, cropEnd.y)),
                    x2: Math.floor(Math.max(cropStart.x, cropEnd.x)),
                    y2: Math.floor(Math.max(cropStart.y, cropEnd.y))
                };
                updatePreview();
            }
        });
        
        drawCropBox(ctx, { x: cropData.x1, y: cropData.y1 }, 
                    { x: cropData.x2, y: cropData.y2 }, scaleX, scaleY, img.offsetWidth, img.offsetHeight);
        updatePreview();
    };
}

function drawCropBox(ctx, start, end, scaleX, scaleY, canvasWidth, canvasHeight) {
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    
    const x1 = start.x / scaleX;
    const y1 = start.y / scaleY;
    const x2 = end.x / scaleX;
    const y2 = end.y / scaleY;
    
    // Draw overlay
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    
    // Clear crop area
    ctx.clearRect(x1, y1, x2 - x1, y2 - y1);
    
    // Draw border
    ctx.strokeStyle = '#667eea';
    ctx.lineWidth = 2;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
}

function updatePreview() {
    const img = document.getElementById('crop-image');
    const preview = document.getElementById('crop-preview');
    
    if (!img.complete) {
        img.onload = updatePreview;
        return;
    }
    
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    const x1 = Math.max(0, Math.floor(cropData.x1));
    const y1 = Math.max(0, Math.floor(cropData.y1));
    const x2 = Math.min(img.naturalWidth, Math.floor(cropData.x2));
    const y2 = Math.min(img.naturalHeight, Math.floor(cropData.y2));
    
    if (x2 <= x1 || y2 <= y1) return;
    
    canvas.width = x2 - x1;
    canvas.height = y2 - y1;
    
    ctx.drawImage(img, x1, y1, x2 - x1, y2 - y1, 0, 0, x2 - x1, y2 - y1);
    
    preview.innerHTML = `<img src="${canvas.toDataURL()}" alt="Crop preview">`;
}

async function setReferenceFace() {
    if (!currentImagePath) {
        alert('No image selected');
        return;
    }
    
    try {
        const response = await fetch('/api/face/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                path: currentImagePath,
                x1: cropData.x1,
                x2: cropData.x2,
                y1: cropData.y1,
                y2: cropData.y2
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('✅ Reference face set successfully!');
            showStep(4);
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function runMatching() {
    const progressDiv = document.getElementById('matching-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    progressDiv.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Starting matching process...';
    
    try {
        const response = await fetch('/api/match/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ images: allImages })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            progressFill.style.width = '100%';
            progressText.textContent = 'Matching complete!';
            
            matchingResults = data.results;
            displayResults(data);
            showStep(5);
        } else {
            alert('Error: ' + data.error);
            progressDiv.style.display = 'none';
        }
    } catch (error) {
        alert('Error: ' + error.message);
        progressDiv.style.display = 'none';
    }
}

function displayResults(data) {
    document.getElementById('matched-count').textContent = data.matched;
    document.getElementById('total-count').textContent = data.total;
    document.getElementById('match-rate').textContent = 
        ((data.matched / data.total) * 100).toFixed(1) + '%';
    
    const tbody = document.getElementById('results-body');
    tbody.innerHTML = '';
    
    data.results.forEach(result => {
        const tr = document.createElement('tr');
        
        const similarity = result.max_similarity;
        // colour against the threshold the server actually used, or the badges
        // contradict the Match/No Match column sitting next to them
        const thr = data.threshold;
        let simClass = 'similarity-low';
        if (similarity >= thr) simClass = 'similarity-high';
        else if (similarity >= thr - 0.1) simClass = 'similarity-medium';
        
        const imageUrl = '/api/image?path=' + encodeURIComponent(result.image_path.replace(/\\/g, '/'));
        tr.innerHTML = `
            <td><img src="${imageUrl}" style="max-width: 100px; height: auto; border-radius: 4px;" onerror="this.style.display='none'"></td>
            <td style="max-width: 300px; word-break: break-all;">${result.image_path}</td>
            <td><span class="similarity-badge ${simClass}">${(similarity * 100).toFixed(1)}%</span></td>
            <td>${result.faces}</td>
            <td class="${result.is_match ? 'match-yes' : 'match-no'}">
                ${result.is_match ? '✓ Match' : '✗ No Match'}
            </td>
        `;
        
        tbody.appendChild(tr);
    });
}

async function exportMatches() {
    const folderName = document.getElementById('export-folder').value.trim();
    
    if (!folderName) {
        alert('Please enter a folder name');
        return;
    }
    
    const statusDiv = document.getElementById('export-status');
    statusDiv.textContent = 'Exporting...';
    statusDiv.className = '';
    
    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder_name: folderName,
                results: matchingResults
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.textContent = `✅ Exported ${data.exported} images to ${data.folder}`;
            statusDiv.className = 'export-success';
            showStep(6);
        } else {
            statusDiv.textContent = 'Error: ' + data.error;
            statusDiv.className = 'export-error';
        }
    } catch (error) {
        statusDiv.textContent = 'Error: ' + error.message;
        statusDiv.className = 'export-error';
    }
}

function showStep(stepNumber) {
    for (let i = 1; i <= 6; i++) {
        const step = document.getElementById(`step${i}`);
        if (step) {
            step.style.display = i === stepNumber ? 'block' : 'none';
        }
    }
}

