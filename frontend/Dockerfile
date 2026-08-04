# 前端生产镜像：多阶段构建
# 阶段 1：构建 React 应用（产出 dist/）
FROM node:20-alpine AS build

WORKDIR /app

# 先复制依赖清单，利用 Docker 缓存层
COPY package.json package-lock.json ./
RUN npm ci

# 复制源码并构建
COPY . .
RUN npm run build

# 阶段 2：Nginx 托管静态资源 + 反向代理 /api 到后端
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
