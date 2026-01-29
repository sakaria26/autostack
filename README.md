<img width="500" alt="logo" src="autostack/src/assets/images/logo.png">

# Autostack

A prototype for creating the necessary infrastructure for developing and deploying your projects.

## Installation

### Supported Operating Systems

- Linux
- Windows (Through WSL)

### System Requirements

- [Docker](https://docs.docker.com/desktop/setup/install/linux/)
- [Devbox](https://www.jetify.com/docs/devbox/installing-devbox/)
- [Node.js](https://nodejs.org/en/download/current/)
- [Python](https://www.python.org/downloads/)
- [Poetry](https://python-poetry.org/docs/#installation/)

Run the following commands to setup the project locally on your machine:
 
### ⚡ Simplified Setup (Recommended)
 
We now provide a unified Python CLI to handle installation, diagnostics, and running the entire stack automatically.
 
```bash
python3 autostack.py
```
 
**Features:**
- **Automated setup**: Detects and installs missing dependencies for both backend and frontend.
- **Smart Launch**: Starts Docker services, the backend gateway, and the frontend development server in one command.
- **Self-Healing**: Detects port conflicts and provides diagnostics for Docker and MongoDB.
- **Maintenance**: built-in Docker pruning and system cleanup.
 
---
 
### 🛠️ Manual Backend Setup

Open a terminal and navigate to the backend directory:

```bash
cd autostack-engine
```

Install Python dependencies:

```bash
poetry install
```

Start the database and Redis cache:

```bash
docker compose -f deployments/docker/compose.yml up -d --build
```

Configure environment variables:

```bash
cp .env.copy .env
```

Edit the `.env` file and add your `GEMINI_API_KEY`. You can create a free API key at [https://aistudio.google.com/app/api-keys](https://aistudio.google.com/app/api-keys).

Set up database

```bash
poetry run setup-database
```

```bash
poetry run migrate-database
```

Run the backend gateway:

```bash
poetry run gateway
```

### 2. Frontend

Open a separate terminal and navigate to the frontend directory:

```bash
cd autostack
```

Install frontend dependencies:

```bash
npm install
```

Start the Angular development server:

```bash
ng serve
```

## Usage

Once both the backend and frontend are running, navigate to [http://localhost:4200](http://localhost:4200) in your browser to start using the system.

## Testing & Data Export

After testing the system, you can export your data for analysis:

1. Navigate to the MongoDB Compass UI at [http://127.0.0.1:8081/](http://127.0.0.1:8081/)
2. Export the following collections:
   - project_chat
   - schema_rating
   - service_logs
   - Any other relevant database information you're comfortable sharing
3. Zip all exported files and upload the exported data to [this survey](https://forms.gle/1vYwG1y1dyhiKy2Y9)

Thank you for participating in this research
