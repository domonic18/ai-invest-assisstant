# 独立数据库迁移镜像（路线 C）
#
# 目的：迁移文件随镜像版本化，部署时不再向宿主机同步迁移文件——
#       线上执行的迁移内容由 APP_TAG 唯一决定，与应用代码同 commit、同版本。
#
# 基础镜像说明：
#   postgres:16-alpine —— 只为拿到 psql 客户端；容器不跑数据库
#   （VOLUME /var/lib/postgresql/data 随容器创建，容器 --rm 退出时自动回收）
FROM postgres:16-alpine

# 迁移 SQL 与 runner 一并打进镜像：二者同版本，不会出现「新 SQL + 旧脚本」的错配
COPY docker/database/migrations /migrations
COPY docker/database/migrate.sh /usr/local/bin/migrate.sh

# legacy/ 是历史归档，永不执行；剔除以免镜像里留一份会误导人的旧迁移
RUN rm -rf /migrations/legacy \
    && chmod 755 /usr/local/bin/migrate.sh

# 迁移目录由镜像固定；PGHOST/PGUSER/PGPASSWORD/PGDATABASE 由 compose 注入
ENV MIGRATIONS_DIR=/migrations

ENTRYPOINT ["/usr/local/bin/migrate.sh"]
