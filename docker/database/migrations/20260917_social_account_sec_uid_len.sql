-- 抖音新账号 sec_uid 可超 64 字符（存量 55），登记「李大霄」时入库 500
-- （StringDataRightTruncationError）。放宽到 128；重复执行同类型为 no-op，天然幂等。

ALTER TABLE social_account ALTER COLUMN sec_uid TYPE VARCHAR(128);
