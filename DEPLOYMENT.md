# PythonAnywhere Deployment Guide

## Prerequisites

- GitHub account with NerdPool repository
- PythonAnywhere account (free or paid)
- Local `np_data.db` file ready for upload

---

## Step 1: Prepare Local Repository

### 1.1 Verify .gitignore

Ensure `.gitignore` excludes test files and databases:

```bash
cd c:\Users\seanj\AntiGravityProjects\NerdPool
cat .gitignore  # Verify test scripts and *.db are listed
```

### 1.2 Check Git Status

```bash
git status
```

You should see only essential app files ready to commit.

### 1.3 Commit and Push

```bash
git add .
git commit -m "NerdPool v3 - Production ready with multi-carpool support"
git push origin main
```

---

## Step 2: Set Up PythonAnywhere

### 2.1 Create Account

1. Go to https://www.pythonanywhere.com
2. Sign up for free account (or use existing)
3. Note your username (you'll need it for URLs)

### 2.2 Open Bash Console

1. Click "Consoles" tab
2. Click "Bash" to start a new console

---

## Step 3: Clone Repository

In the PythonAnywhere Bash console:

```bash
# Clone your repository (replace YOUR_USERNAME)
git clone https://github.com/YOUR_USERNAME/NerdPool.git

# Navigate to project
cd NerdPool

# Verify files
ls -la
```

You should see all your Python files but NO database files.

---

## Step 4: Set Up Virtual Environment

```bash
# Create virtual environment with Python 3.10
python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

You should see Flask and other dependencies installed.

---

## Step 5: Upload Database

**CRITICAL**: The database file is NOT in git and must be uploaded manually.

### Option A: Upload via Files Tab (Recommended)

1. Click "Files" tab in PythonAnywhere
2. Navigate to `/home/YOUR_USERNAME/NerdPool/`
3. Click "Upload a file" button
4. Select your local `np_data.db` file
5. Wait for upload to complete
6. Verify file appears in directory listing

### Option B: Fresh Migration (Alternative)

If you prefer to migrate from legacy database:

```bash
cd ~/NerdPool

# Upload data.db first (via Files tab)
# Then run migration
source venv/bin/activate
python migrate_legacy_fresh.py
```

**IMPORTANT**: If using fresh migration, you MUST change default passwords after deployment!

---

## Step 6: Configure Web App

### 6.1 Create Web App

1. Click "Web" tab
2. Click "Add a new web app"
3. Click "Next" (accept domain name)
4. Select "Manual configuration"
5. Select "Python 3.10"
6. Click "Next"

### 6.2 Configure Virtual Environment

In the "Web" tab, find "Virtualenv" section:

1. Enter path: `/home/YOUR_USERNAME/NerdPool/venv`
2. Click checkmark to save

### 6.3 Configure WSGI File

1. In "Web" tab, find "Code" section
2. Click on WSGI configuration file link (e.g., `/var/www/YOUR_USERNAME_pythonanywhere_com_wsgi.py`)
3. **Delete all existing content**
4. Replace with:

```python
import sys
import os

# Add project directory to sys.path
project_home = '/home/YOUR_USERNAME/NerdPool'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set working directory
os.chdir(project_home)

# Import Flask app
from app_v3 import app as application
```

**IMPORTANT**: Replace `YOUR_USERNAME` with your actual PythonAnywhere username!

5. Click "Save" button (top right)

### 6.4 Set Working Directory

In "Web" tab, find "Code" section:

1. Set "Working directory" to: `/home/YOUR_USERNAME/NerdPool`
2. Click checkmark to save

---

## Step 7: Reload and Test

### 7.1 Reload Web App

1. Scroll to top of "Web" tab
2. Click green "Reload YOUR_USERNAME.pythonanywhere.com" button
3. Wait for reload to complete

### 7.2 Visit Your App

1. Click the link: `YOUR_USERNAME.pythonanywhere.com`
2. You should see the login page

### 7.3 Test Login

Try logging in with one of your users:
- Username: `sean` (or your admin username)
- Password: (your password, or `change-me-sean` if fresh migration)

---

## Step 8: Post-Deployment Configuration

### 8.1 Change Default Passwords

If you used `migrate_legacy_fresh.py`, change these passwords immediately:

1. Log in as each user
2. Go to Account page
3. Use "Change password" form
4. Set strong passwords

Default passwords from fresh migration:
- `christian`: `change-me-christian`
- `eric`: `change-me-eric`
- `sean`: `change-me-sean`

### 8.2 Verify Features

Test all major features:

- ✅ Schedule page displays correctly
- ✅ Carpool selector dropdown works
- ✅ Can switch between carpools
- ✅ History page shows data
- ✅ Date filtering works
- ✅ Admin pages accessible (if admin)
- ✅ Audit log shows entries with carpool names
- ✅ Can save role changes

### 8.3 Create Test Entry

1. Go to Schedule page
2. Select today's date
3. Set roles for members
4. Click "Save"
5. Verify entry appears in History

---

## Step 9: Database Backups

### 9.1 Manual Backup

In PythonAnywhere Bash console:

```bash
cd ~/NerdPool
cp np_data.db np_data_backup_$(date +%Y%m%d).db
```

### 9.2 Download Backup

1. Go to "Files" tab
2. Navigate to `/home/YOUR_USERNAME/NerdPool/`
3. Click on backup file (e.g., `np_data_backup_20251202.db`)
4. Click "Download" button
5. Save to your local machine

### 9.3 Schedule Regular Backups

Consider setting up a scheduled task:

1. Go to "Tasks" tab
2. Create daily task:
   ```bash
   cd ~/NerdPool && cp np_data.db backups/np_data_$(date +\%Y\%m\%d).db
   ```

---

## Updating the Application

### When You Make Changes Locally

```bash
# On your local machine
cd c:\Users\seanj\AntiGravityProjects\NerdPool
git add .
git commit -m "Description of changes"
git push origin main
```

### Deploy Updates to PythonAnywhere

```bash
# In PythonAnywhere Bash console
cd ~/NerdPool
git pull origin main

# If requirements.txt changed:
source venv/bin/activate
pip install -r requirements.txt
```

Then reload web app from "Web" tab.

---

## Troubleshooting

### Error: "Something went wrong :("

**Check Error Log:**
1. Go to "Web" tab
2. Scroll to "Log files" section
3. Click "Error log" link
4. Look for Python errors at the bottom

**Common Issues:**

**Import Error:**
```
ModuleNotFoundError: No module named 'flask'
```
**Fix:** Verify virtual environment path in Web tab

**Database Error:**
```
sqlite3.OperationalError: unable to open database file
```
**Fix:** 
- Verify `np_data.db` exists in `/home/YOUR_USERNAME/NerdPool/`
- Check file permissions: `chmod 644 np_data.db`

**Path Error:**
```
ImportError: No module named 'app_v3'
```
**Fix:** Verify working directory and WSGI file paths

### App Loads But Can't Login

**Check Database:**
```bash
cd ~/NerdPool
sqlite3 np_data.db "SELECT username FROM users;"
```

If no users exist, you need to create them or re-upload database.

### Static Files Not Loading

If you add CSS/JS files later:

1. Create `static/` directory in project
2. In "Web" tab, add static files mapping:
   - URL: `/static/`
   - Directory: `/home/YOUR_USERNAME/NerdPool/static/`

### Performance Issues

Free PythonAnywhere accounts have limitations:
- CPU seconds per day
- Slower response times
- Consider upgrading for production use

---

## Security Best Practices

### 1. Use Strong Passwords
- Change all default passwords
- Use unique passwords for each user
- Consider password manager

### 2. Regular Backups
- Download database weekly
- Keep multiple backup versions
- Store backups securely

### 3. Monitor Access
- Check error logs regularly
- Review audit logs for suspicious activity
- Monitor user activity

### 4. Keep Updated
- Update dependencies regularly: `pip install --upgrade -r requirements.txt`
- Pull latest code from GitHub
- Test updates before deploying

---

## Custom Domain (Optional)

To use your own domain instead of `YOUR_USERNAME.pythonanywhere.com`:

1. Upgrade to paid PythonAnywhere account
2. Go to "Web" tab
3. Add custom domain
4. Update DNS records with your domain registrar
5. Follow PythonAnywhere's domain setup guide

---

## Support Resources

- **PythonAnywhere Help**: https://help.pythonanywhere.com
- **PythonAnywhere Forums**: https://www.pythonanywhere.com/forums/
- **Flask Documentation**: https://flask.palletsprojects.com/
- **SQLite Documentation**: https://www.sqlite.org/docs.html

---

## Quick Reference

### Essential Paths
- Project: `/home/YOUR_USERNAME/NerdPool`
- Virtual env: `/home/YOUR_USERNAME/NerdPool/venv`
- Database: `/home/YOUR_USERNAME/NerdPool/np_data.db`
- WSGI: `/var/www/YOUR_USERNAME_pythonanywhere_com_wsgi.py`

### Essential Commands
```bash
# Activate virtual environment
source ~/NerdPool/venv/bin/activate

# Pull latest code
cd ~/NerdPool && git pull

# Backup database
cd ~/NerdPool && cp np_data.db np_data_backup_$(date +%Y%m%d).db

# Check database
sqlite3 ~/NerdPool/np_data.db "SELECT COUNT(*) FROM entries;"
```

### After Every Code Update
1. `git pull` in Bash console
2. Reload web app from "Web" tab
3. Test in browser
