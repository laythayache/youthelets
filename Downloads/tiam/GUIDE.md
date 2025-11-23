# 🎯 Face Matching System - Complete Guide

A modern web application for face recognition and matching across photo collections, with Google Drive integration.

---

## 📋 Table of Contents

1. [Features](#features)
2. [Local Setup](#local-setup)
3. [Free Hosting Deployment](#free-hosting-deployment)
4. [Usage Guide](#usage-guide)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)

---

## ✨ Features

- 🎯 **Face Detection & Matching**: Uses InsightFace for accurate face recognition
- ☁️ **Google Drive Integration**: Connect and load images directly from Google Drive
- 📁 **Local Folder Support**: Also works with local file system folders
- 🖼️ **Interactive UI**: Modern, responsive red-themed web interface
- ✂️ **Face Cropping**: Interactive crop tool to select reference faces
- 📊 **Results Dashboard**: View matching results with similarity scores
- 📤 **Export Functionality**: Export matched images to organized folders

---

## 🖥️ Local Setup

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: If you're on Windows and get errors installing InsightFace, you need Microsoft C++ Build Tools:
1. Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Install with "C++ build tools" workload
3. Then run: `pip install insightface==0.7.3`

### Step 2: Google Drive API Setup (Optional)

#### Option A: OAuth 2.0 (User Authentication)

For personal Google Drive access:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Drive API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Choose **Web application**
6. Add `http://localhost:5000/auth/callback` to **Authorized redirect URIs**
7. Download the credentials JSON file
8. Rename it to `client_secrets.json` and place it in the project root

#### Option B: Service Account (For Shared Drives - Recommended for Production)

For allowing users to access shared Drive folders without authentication:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select your project and enable **Google Drive API**
3. Go to **Credentials** → **Create Credentials** → **Service Account**
4. Create a service account (or use existing)
5. Click on the service account → **Keys** tab → **Add Key** → **Create new key** → **JSON**
6. Download the JSON file and save as `service_account.json` in project root
7. **Important**: Share your Drive folder with the service account email
   - Right-click folder in Google Drive → **Share**
   - Add the service account email (from the JSON file, `client_email` field)
   - Give it **Viewer** access
8. Set environment variable or create `config.json`:
   ```json
   {
     "youtheletes_drive_folder_id": "your-folder-id-here"
   }
   ```
   Or set: `YOUTHELETES_DRIVE_FOLDER_ID=your-folder-id`

**Security Note**: `service_account.json` contains private keys. It's automatically ignored by git, but never commit it to public repositories!

### Step 3: Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

**First Run**: InsightFace models will download automatically (takes 5-10 minutes). Be patient!

---

## 🚀 Free Hosting Deployment

### Option 1: Render.com (Recommended - Easiest)

**Free Tier**: 750 hours/month

#### Steps:

1. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

2. **Deploy on Render**:
   - Go to [render.com](https://render.com) and sign up (free)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - **Name**: `face-matching-app` (or any name)
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
     - **Plan**: Free
   - Add Environment Variable:
     - Key: `SECRET_KEY`
     - Value: Generate with `python -c "import secrets; print(secrets.token_hex(32))"`
   - Click "Create Web Service"
   - Wait 10-15 minutes for first deployment

3. **Update Google Drive OAuth** (if using):
   - Go to Google Cloud Console
   - Edit OAuth credentials
   - Add: `https://your-app.onrender.com/auth/callback` to redirect URIs

**Your app will be live at**: `https://your-app-name.onrender.com`

**Note**: Free tier spins down after 15 min inactivity. First request after spin-down takes ~30 seconds.

---

### Option 2: Railway.app (Simple)

**Free Tier**: $5 credit/month

#### Steps:

1. **Push to GitHub** (same as above)

2. **Deploy on Railway**:
   - Go to [railway.app](https://railway.app) and sign up
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository
   - Railway auto-detects Python projects
   - Add Environment Variable:
     - Key: `SECRET_KEY`
     - Value: Your random secret key
   - Railway automatically deploys

**Your app will be live at**: `https://your-app.up.railway.app`

---

### Option 3: Fly.io (Performance)

**Free Tier**: 3 shared VMs

#### Steps:

1. **Install Fly CLI**:
   ```bash
   # Windows PowerShell
   iwr https://fly.io/install.ps1 -useb | iex
   ```

2. **Create App**:
   ```bash
   fly auth login
   fly launch
   ```

3. **Set Environment Variables**:
   ```bash
   fly secrets set SECRET_KEY=your-secret-key
   fly secrets set FLASK_ENV=production
   ```

4. **Deploy**:
   ```bash
   fly deploy
   ```

**Your app will be live at**: `https://your-app-name.fly.dev`

---

### Deployment Checklist

Before deploying:

- [ ] Code pushed to GitHub
- [ ] `SECRET_KEY` generated (use: `python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Google Drive OAuth updated (if using) - add production URL to redirect URIs
- [ ] Tested locally first
- [ ] All files committed to git

### Important Notes

- **First Deployment**: Takes 10-15 minutes (downloading InsightFace models ~500MB)
- **Free Tier Limits**: Limited CPU/memory - face matching may be slow
- **Storage**: Models are cached, subsequent deployments are faster
- **Security**: Always set a strong `SECRET_KEY` in production

---

## 📖 Usage Guide

### Step 1: Select Data Source

**Local Folders**:
- Enter paths to folders containing images
- Example: `C:/Users/Photos/Events`

**Google Drive**:
- Click "Authenticate Google Drive"
- Authorize the application
- Enter Google Drive folder IDs
- To get folder ID: Right-click folder → Get link → Extract ID from URL

### Step 2: Select Reference Image

- Browse through the image gallery (paginated, 20 per page)
- Click on an image to select it as reference
- Use Previous/Next buttons to navigate

### Step 3: Crop Reference Face

- Use your mouse to drag and select the face region
- Preview updates in real-time
- Click "🎯 Set Reference Face" when done
- The system will detect faces in the cropped region

### Step 4: Run Face Matching

- Click "🔍 Run Matching" to process all images
- Progress bar shows processing status
- The system compares faces using cosine similarity
- Results show similarity scores (0-100%)

### Step 5: View Results

- See matching statistics:
  - **Matched**: Number of images with matching faces
  - **Total**: Total images processed
  - **Match Rate**: Percentage of matches
- View detailed results table with:
  - Image thumbnails
  - Similarity scores
  - Number of faces detected
  - Match status

### Step 6: Export Matched Images

- Enter a folder name (default: `matched_photos`)
- Click "📂 Export Matches"
- Matched images will be copied to the output directory
- Images are organized in subfolders

---

## ⚙️ Configuration

### Environment Variables

- `SECRET_KEY`: Flask secret key (required for production)
- `FLASK_ENV`: Set to `production` for production, `development` for local
- `PORT`: Server port (default: 5000, auto-set by hosting platforms)

### Application Settings

Edit in `app.py`:

- `SIM_THRESHOLD`: Similarity threshold for matches (default: 0.35)
  - Lower = more matches (may include false positives)
  - Higher = fewer matches (more strict)
- `BATCH`: Batch size for processing (default: 128)
- `PAGE_SIZE`: Images per gallery page (default: 20)
- `MAX_CONTENT_LENGTH`: Max file size (default: 100MB)

### Model Settings

- **Model**: `buffalo_l` (InsightFace)
- **Detection Size**: 640x640 pixels
- **GPU Support**: Automatically uses CUDA if available, falls back to CPU

---

## 🔧 Troubleshooting

### Local Setup Issues

**InsightFace Installation Fails**:
- Install Microsoft C++ Build Tools (Windows)
- Or use pre-built wheels: `pip install --only-binary :all: insightface`
- See `SETUP_LOCAL.md` for details

**No Face Detected**:
- Ensure cropped region contains a clear, front-facing face
- Good lighting helps
- Face should be reasonably sized in the crop

**GPU Not Detected**:
- Install CUDA-compatible PyTorch if you have NVIDIA GPU
- App works fine on CPU (just slower)

**Path Errors**:
- Use absolute paths for local folders
- Windows: `C:/Users/Photos/Events` (forward slashes work)
- Linux/Mac: `/home/user/photos/events`

### Deployment Issues

**Build Fails**:
- Check `requirements.txt` is correct
- Check platform logs for specific errors
- Verify Python version compatibility (3.11 recommended)

**App Crashes on Startup**:
- Check logs in hosting platform dashboard
- Verify `SECRET_KEY` is set
- First deployment takes time (downloading models)
- Check disk space (models are ~500MB)

**Slow Performance**:
- Free tiers have limited CPU/memory
- Face matching is CPU-intensive
- Consider processing smaller batches
- Upgrade to paid tier for better performance

**Models Not Loading**:
- First run downloads models (10+ minutes)
- Check logs for download progress
- Ensure sufficient disk space
- Models are cached after first download

**Connection Refused**:
- Server may be spinning up (free tiers)
- Wait 30-60 seconds and try again
- Check if service is running in dashboard

### Google Drive Issues

**Authentication Fails**:
- Verify `client_secrets.json` is in project root
- Check redirect URI matches exactly
- Ensure Google Drive API is enabled
- For production: Update redirect URI to production URL

**Can't Access Folders**:
- Verify folder IDs are correct
- Check folder permissions (must be accessible)
- Ensure OAuth scope includes Drive read access

---

## 📝 Technical Details

### Face Detection
- **Library**: InsightFace
- **Model**: buffalo_l
- **Method**: RetinaFace detection + ArcFace recognition
- **Embedding Dimension**: 512

### Similarity Metric
- **Method**: Cosine similarity
- **Range**: -1 to 1 (normalized to 0-100%)
- **Threshold**: 0.35 (configurable)

### Supported Formats
- JPG, JPEG, PNG, WEBP, BMP
- Automatic format detection
- Images resized to max 1280px for processing

### Performance
- **CPU**: ~1-3 seconds per image
- **GPU**: ~0.1-0.5 seconds per image
- **Batch Processing**: Processes in batches of 128 images

---

## 🎨 UI Features

- **Red-Centric Theme**: Modern, vibrant red color scheme
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Smooth Animations**: Polished transitions and hover effects
- **Real-time Preview**: See crop preview as you select
- **Progress Indicators**: Visual feedback during processing
- **Error Messages**: Clear, helpful error notifications

---

## 📞 Need Help?

1. **Check Logs**: Always check application logs first
2. **Test Locally**: Test on localhost before deploying
3. **Read Documentation**: Review platform-specific docs
4. **Check Issues**: Common issues are covered in Troubleshooting section

---

## 🎉 You're Ready!

Your Face Matching System is ready to use! Start locally or deploy to free hosting. Good luck! 🚀

---

## 📄 License

This project is provided as-is for educational and personal use.

