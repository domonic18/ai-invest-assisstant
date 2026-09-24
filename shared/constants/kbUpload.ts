/**
 * 知识库上传策略常量（前后端共享，后端 app/core/config.py 有同名可覆盖项）。
 */

/** 超过该大小走 multipart 分片直传，否则单 PUT。 */
export const KB_MULTIPART_THRESHOLD_BYTES = 64 * 1024 * 1024

/** 默认分片大小（S3 约束：除末片外每片 >= 5MB，分片数 <= 10000）。 */
export const KB_PART_SIZE_BYTES = 16 * 1024 * 1024
