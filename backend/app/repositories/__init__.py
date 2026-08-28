"""Repository layer for data access.

Repositories encapsulate SQLAlchemy query logic. They do not manage
transactions; services own the transaction boundary.

按业务子域分组，与 ``app/services/`` 的域划分保持一致：
market / chain / reports / review / admin / user；
通用 CRUD 基类见 ``base``。
"""
