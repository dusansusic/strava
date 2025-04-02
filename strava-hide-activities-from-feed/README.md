# Strava Hide Activities From Feed

A Docker-based utility that automatically hides your Strava activities from your home feed. I hope this will be added by Strava soon, under Privacy controls.

## Overview

This script connects to your Strava account using OAuth 2.0 and automatically updates recent activities to hide them from the home feed. This is useful if you want to keep your activities private without completely hiding them.

## Features

- Automatically detects and hides recent activities from your Strava feed
- OAuth 2.0 authentication with token refresh
- Configurable lookback period to process recent activities
- Docker containerized for easy deployment
- Persistent token storage

## Prerequisites

- Docker and Docker Compose
- Strava account with registered API application

## Setup

1. Clone this repository
2. Create a `tokens` directory in the project root to store authentication tokens
3. Set up environment variables (optional, defaults are provided in docker-compose.yml)

## Configuration

The following environment variables can be configured in the docker-compose.yml file:

- `CLIENT_ID`: Your Strava API application client ID
- `CLIENT_SECRET`: Your Strava API application client secret
- `REDIRECT_URI`: OAuth callback URI (default: http://localhost:8000/callback)
- `TOKEN_FILE`: Path to store the OAuth tokens (default: /app/tokens/.strava_token.json)
- `ACTIVITY_LOOKBACK_MINUTES`: How far back to look for activities to hide (default: 300 minutes/5 hours)

You can also set a custom token storage location by setting the `TOKEN_PATH` environment variable when running docker-compose.

## Usage

Start the container:

```bash
docker-compose up -d
```

On first run, the application will open a browser window for Strava authorization. After authorizing, the application will automatically hide your activities from the home feed.

### Running in Headless Environments

When running on a server or headless environment where a browser can't open automatically:

1. Check the application logs to find the authorization URL
2. Copy this URL and open it in a browser on your local machine
3. Complete the Strava authorization
4. After authorizing, you'll be redirected to a page containing the authentication token
5. Copy this token from your browser and manually create the token file in your tokens directory

This manual authentication is only required on first run or when tokens expire and can't be refreshed.

To stop:

```bash
docker-compose down
```

## Docker Hub

A pre-built Docker image is available on Docker Hub at [hub.docker.com/r/dusansusic/strava-hide-activities](https://hub.docker.com/r/dusansusic/strava-hide-activities).

You can use this image directly in your docker-compose.yml:

```yaml
services:
  strava-hide-activities:
    image: dusansusic/strava-hide-activities:latest
    volumes:
      - ${TOKEN_PATH:-./tokens}:/app/tokens
    environment:
      - CLIENT_ID=your_client_id
      - CLIENT_SECRET=your_client_secret
      # Other environment variables as needed
```

## How It Works

1. Authenticates with Strava using OAuth 2.0
2. Fetches activities created within the configured lookback period
3. Updates each activity with the "hide_from_home" flag
4. Runs continuously, checking for new activities

## Logs

Logs are stored in your home directory as `strava_log.log`.

## License

MIT