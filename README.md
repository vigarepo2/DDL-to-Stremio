# DDL Stremio Addon

A simple, self-hosted Stremio addon to stream from Direct Download Links (DDLs).

## Features
- **Web Interface**: Add DDL links through a secure admin panel.
- **Automatic Metadata**: Parses filenames to fetch movie/TV show details from TMDb.
- **Stremio Integration**: Acts as a proper Stremio addon for your media.
- **Simple & Lightweight**: No complex dependencies like Telegram bots.

## Setup

1.  **Configuration**: Create a `config.env` file with the following variables:
    ```env
    BASE_URL="http://your_server_ip:8000"
    MONGO_URI="your_mongodb_connection_string"
    TMDB_API_KEY="your_themoviedb_api_key"
    ADMIN_USERNAME="your_username"
    ADMIN_PASSWORD="your_password"
    ```

2.  **Run with Docker**:
    ```bash
    docker build -t ddl-stremio .
    docker run -d -p 8000:8000 --env-file config.env ddl-stremio
    ```

3.  **Add Media**:
    - Go to `http://your_server_ip:8000` and log in.
    - Paste your DDL links into the form and submit.

4.  **Add to Stremio**:
    - Go to Stremio's addon page and install from the following URL:
    - `http://your_server_ip:8000/stremio/manifest.json`
