# DDL Stremio Addon V2

A clean, simple, self-hosted Stremio addon to stream from Direct Download Links (DDLs).

## Setup

1.  **Configuration**: Create a file named `config.env` in the project root with the following variables:
    ```env
    # The public URL of your server (e.g., http://your_ip:8000 or [https://your-domain.com](https://your-domain.com))
    BASE_URL=""
    
    # Your MongoDB connection string
    MONGO_URI=""
    
    # Your API key from The Movie Database (TMDb)
    TMDB_API_KEY=""
    
    # Credentials for the admin web panel
    ADMIN_USERNAME="admin"
    ADMIN_PASSWORD="admin"
    ```

2.  **Run with Docker**:
    ```bash
    docker build -t ddl-stremio .
    docker run -d --env-file config.env -p 8000:8000 ddl-stremio
    ```

3.  **Add Media**:
    - Go to your server's URL (e.g., `http://localhost:8000`) and log in.
    - Paste your DDL links into the form and submit. The filename in the URL must be properly named for metadata fetching (e.g., `Movie.Title.2024.1080p.mkv`).

4.  **Add to Stremio**:
    - Open Stremio, go to the Addons page, and install from URL. Use the following link:
    - `http://your_server_url:8000/stremio/manifest.json`
