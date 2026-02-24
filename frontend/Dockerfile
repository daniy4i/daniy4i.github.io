FROM node:20-alpine
WORKDIR /app
COPY package.json tsconfig.json next.config.js next-env.d.ts ./
COPY app ./app
COPY lib ./lib
RUN npm install
CMD ["npm","run","dev"]
