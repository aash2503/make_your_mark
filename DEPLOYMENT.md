# Deployment Guide

## 1. Prepare your GitHub repository

1. Commit your project files and push to GitHub.
2. Ensure `requirements.txt`, `packages.txt`, `app.py`, `README.md`, and `static/` are in the repo.

## 2. Configure Google OAuth

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Under **APIs & Services**, go to **OAuth consent screen**.
4. Configure the consent screen for internal or external use.
5. Under **Credentials**, create an **OAuth 2.0 Client ID**.
   - Application type: **Web application**
   - Authorized redirect URIs:
     - `http://localhost:8501`
     - `https://<your-app-name>.streamlit.app`
6. Copy the **Client ID** and **Client Secret**.

## 3. Add Streamlit secrets

Create `.streamlit/secrets.toml` with:

```toml
google_api_key = "YOUR_GEMINI_API_KEY"
gemini_model = "gemini-3.1-flash-lite"
google_oauth_client_id = "YOUR_GOOGLE_OAUTH_CLIENT_ID"
google_oauth_client_secret = "YOUR_GOOGLE_OAUTH_CLIENT_SECRET"
google_oauth_redirect_uri = "https://<your-app-name>.streamlit.app"
pin_code = ""
```

For local testing, use `http://localhost:8501` as the redirect URI.

## 4. Deploy to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io).
2. Click **New app**.
3. Choose your GitHub repository and branch `main`.
4. Set the app file to `app.py`.
5. In **Advanced settings > Secrets**, add the same values from `.streamlit/secrets.toml`.
6. Click **Deploy**.

## 5. Verify app behavior

- Open the deployed URL.
- Test Google sign-in.
- Upload a student submission.
- Generate a feedback PDF.
- Use the **Upload to Google Drive** button.

## 6. What to do if upload fails

- Confirm the OAuth client redirect URI matches the app URL.
- Confirm `google_oauth_client_id` and `google_oauth_client_secret` are correct.
- Confirm the app requested the `drive.file` scope.
- If needed, inspect Streamlit logs for auth or Drive API errors.

## Additional notes

- `packages.txt` installs `tesseract-ocr` and LaTeX packages on Streamlit Cloud.
- `static/manifest.json` and `static/sw.js` enable basic PWA behavior.
- The app serves static files from `/static/`.
