FROM node:16-alpine as builder

RUN apk add --no-cache openjdk11
RUN npm install -g @openapitools/openapi-generator-cli

WORKDIR /app

COPY tools/api/ ./tools/api
COPY lib ./lib
RUN ./tools/api/gen_api.sh ./tools/api/openapi.yml ./lib/mibs/ts

COPY projects/web/package*.json ./
RUN npm install
COPY projects/web/ ./
RUN npm run build

FROM nginx:1.18-alpine
COPY --from=builder /app/build /data/app/
COPY projects/web/nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
