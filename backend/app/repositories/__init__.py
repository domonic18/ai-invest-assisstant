"""数据访问仓储层。

仓储封装 SQLAlchemy 查询逻辑，不管理事务；
事务边界由服务层负责。

按业务子域分组，与 ``app/services/`` 的域划分保持一致：
market / chain / reports / review / admin / user；
通用 CRUD 基类见 ``base``。
"""
