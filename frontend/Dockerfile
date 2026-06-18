# Development image for the React frontend
FROM node:20-bullseye-slim

WORKDIR /app

# Install system packages that some frontend dependencies may need when npm
# installs native or prebuilt binaries in the container.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3 \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first so they can be cached between source changes.
COPY package.json package-lock.json ./
RUN npm ci

# Copy the source tree. In docker-compose we bind-mount the project over this
# path so changes on the host reflect immediately in the running dev server.
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
