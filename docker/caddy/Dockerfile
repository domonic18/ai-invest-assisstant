# 生产入口反代镜像：alpine + 官方打包的 caddy。
# 第三方镜像 registry 直拷入 TCR 三次被国内镜像源中断（manifest EOF/超时），
# 改为源构建——基础镜像与 apk 源均为境内稳定路径，产出确定 linux/amd64。
FROM alpine:3.20

# apk 换阿里云源：dl-cdn.alpinelinux.org 境内不可靠
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories \
 && apk add --no-cache caddy

COPY docker/caddy/Caddyfile /etc/caddy/Caddyfile

EXPOSE 80 443
ENTRYPOINT ["caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
