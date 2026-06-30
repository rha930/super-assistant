FROM node:20-alpine

WORKDIR /app

# Bypass SSL cert issues (corporate proxy/VPN)
RUN npm config set strict-ssl false

# Install dependencies (layer cache)
COPY package.json package-lock.json ./
RUN npm ci || npm install

# Copy application source
COPY . .

EXPOSE 5173

CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"]
