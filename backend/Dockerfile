FROM node:18-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --production || npm install --production --legacy-peer-deps
COPY . .
EXPOSE 3001
CMD ["npm", "start"]
