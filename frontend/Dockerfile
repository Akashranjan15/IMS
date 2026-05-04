FROM node:22-alpine

WORKDIR /app

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_API_TOKEN=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_API_TOKEN=$VITE_API_TOKEN

COPY package.json .
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--port", "3000"]

