# Dockerfile for React frontend (Phase 1.4)
# Development image – runs Vite dev server on port 3000

FROM node:20-alpine

WORKDIR /app

# Install dependencies (package.json only for layer caching)
COPY package.json .
RUN npm install

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 3000

# Run Vite dev server, listening on all interfaces
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
