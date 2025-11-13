import psycopg2
import psycopg2.pool
import logging
import os
import time
import json
from datetime import datetime
from contextlib import contextmanager

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """
    数据库操作的基础异常类
    """
    def __init__(self, message, error_code=None, original_error=None):
        self.message = message
        self.error_code = error_code
        self.original_error = original_error
        self.timestamp = datetime.now().isoformat()
        super().__init__(self.message)


class ConnectionError(DatabaseError):
    """
    数据库连接相关的异常
    """
    pass


class QueryError(DatabaseError):
    """
    数据库查询相关的异常
    """
    pass


class TransactionError(DatabaseError):
    """
    数据库事务相关的异常
    """
    pass



class PostgreSQLManager:
    """
    PostgreSQL数据库管理类，提供数据库连接、查询和事务管理功能
    """
    
    def __init__(self, dbname=None, user=None, password=None, host=None, port=None):
        """
        初始化数据库管理器
        
        Args:
            dbname: 数据库名称
            user: 数据库用户名
            password: 数据库密码
            host: 数据库主机地址
            port: 数据库端口
        """
        # 从环境变量或参数中获取数据库配置
        self.dbname = dbname or os.getenv('DB_NAME', 'hsbc_campaign')
        self.user = user or os.getenv('DB_USER', 'postgres')
        self.password = password or os.getenv('DB_PASSWORD', '')
        self.host = host or os.getenv('DB_HOST', 'localhost')
        self.port = port or os.getenv('DB_PORT', '5432')
        
        # 连接池配置
        self.min_conn = int(os.getenv('DB_MIN_CONN', '1'))
        self.max_conn = int(os.getenv('DB_MAX_CONN', '10'))
        self.connection_pool = None
        self._initialize_pool()
        
        # 连接池统计信息
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'connection_errors': 0,
            'last_error_time': None
        }
    
    def _initialize_pool(self):
        """
        初始化数据库连接池
        """
        try:
            # 创建连接池
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=self.min_conn,
                maxconn=self.max_conn,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                # 添加连接参数
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            logger.info(
                "数据库连接池初始化成功",
                extra={
                    'min_conn': self.min_conn,
                    'max_conn': self.max_conn,
                    'dbname': self.dbname,
                    'host': self.host
                }
            )
            self.stats['total_connections'] = 0
            self.stats['active_connections'] = 0
        except psycopg2.OperationalError as e:
            error_msg = f"数据库连接池初始化失败: 操作错误 - {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'error_type': 'OperationalError',
                    'dbname': self.dbname,
                    'host': self.host
                }
            )
            self.stats['connection_errors'] += 1
            self.stats['last_error_time'] = time.time()
            raise ConnectionError(error_msg, error_code='DB_CONN_001', original_error=e)
        except psycopg2.ProgrammingError as e:
            error_msg = f"数据库连接池初始化失败: 配置错误 - {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'error_type': 'ProgrammingError',
                    'dbname': self.dbname
                }
            )
            self.stats['connection_errors'] += 1
            self.stats['last_error_time'] = time.time()
            raise ConnectionError(error_msg, error_code='DB_CONN_002', original_error=e)
        except Exception as e:
            error_msg = f"数据库连接池初始化失败: 未知错误 - {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'error_type': type(e).__name__
                }
            )
            self.stats['connection_errors'] += 1
            self.stats['last_error_time'] = time.time()
            raise ConnectionError(error_msg, error_code='DB_CONN_003', original_error=e)
    
    @contextmanager
    def get_connection(self):
        """
        获取数据库连接的上下文管理器
        
        Yields:
            psycopg2.connection: 数据库连接对象
        """
        connection = None
        retry_count = 0
        max_retries = 3
        retry_delay = 1
        
        while retry_count <= max_retries:
            try:
                if not self.connection_pool:
                    logger.warning("连接池不存在，重新初始化")
                    self._initialize_pool()
                
                connection = self.connection_pool.getconn()
                self.stats['active_connections'] += 1
                self.stats['total_connections'] += 1
                
                # 检查连接是否健康
                if not self._is_connection_healthy(connection):
                    logger.warning("检测到不健康的连接，重新创建")
                    if connection:
                        connection.close()
                    continue
                
                yield connection
                break
            except psycopg2.OperationalError as e:
                retry_count += 1
                logger.warning(f"数据库连接操作错误 (尝试 {retry_count}/{max_retries}): {str(e)}")
                self.stats['connection_errors'] += 1
                self.stats['last_error_time'] = time.time()
                
                # 如果是最后一次尝试失败，重新初始化连接池
                if retry_count > max_retries:
                    logger.error("达到最大重试次数，重新初始化连接池")
                    self._initialize_pool()
                    raise
                
                time.sleep(retry_delay * retry_count)  # 指数退避
            except Exception as e:
                logger.error(f"获取数据库连接失败: {str(e)}")
                self.stats['connection_errors'] += 1
                self.stats['last_error_time'] = time.time()
                raise
            finally:
                if connection:
                    # 归还连接到池中前检查是否仍然有效
                    try:
                        if not self._is_connection_healthy(connection):
                            logger.warning("归还前检测到不健康的连接，关闭而不归还")
                            connection.close()
                        else:
                            self.connection_pool.putconn(connection)
                    except:
                        # 如果归还失败，至少减少活跃连接计数
                        pass
                    self.stats['active_connections'] = max(0, self.stats['active_connections'] - 1)
    
    @contextmanager
    def get_cursor(self, connection=None, commit=False):
        """
        获取数据库游标
        
        Args:
            connection: 数据库连接对象，如果不提供则从连接池获取
            commit: 是否在结束时自动提交事务
            
        Yields:
            psycopg2.cursor: 数据库游标对象
        """
        own_connection = connection is None
        if own_connection:
            conn_context = self.get_connection()
            connection = next(conn_context.__enter__())
        
        cursor = None
        try:
            cursor = connection.cursor()
            yield cursor
            
            if commit:
                connection.commit()
        except Exception as e:
            if commit:
                connection.rollback()
            logger.error(f"游标操作失败: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()
            if own_connection:
                conn_context.__exit__(None, None, None)
    
    def _is_connection_healthy(self, connection):
        """
        检查连接是否健康
        
        Args:
            connection: 数据库连接对象
            
        Returns:
            bool: 连接是否健康
        """
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except:
            return False
    
    def close_pool(self):
        """
        关闭数据库连接池
        """
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("数据库连接池已关闭")
            self.stats['active_connections'] = 0
    
    def get_pool_stats(self):
        """
        获取连接池统计信息
        
        Returns:
            dict: 连接池统计数据
        """
        return self.stats.copy()
    
    def refresh_pool(self):
        """
        刷新连接池（重新创建）
        """
        logger.info("刷新数据库连接池")
        self.close_pool()
        self._initialize_pool()
        return True
    
    def test_connection(self):
        """
        测试数据库连接
        
        Returns:
            bool: 连接是否成功
        """
        start_time = time.time()
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                execution_time = time.time() - start_time
                logger.info(
                    "数据库连接测试成功",
                    extra={
                        'execution_time_ms': round(execution_time * 1000, 2),
                        'dbname': self.dbname,
                        'host': self.host
                    }
                )
                return result == (1,)
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                "数据库连接测试失败",
                extra={
                    'execution_time_ms': round(execution_time * 1000, 2),
                    'dbname': self.dbname,
                    'host': self.host,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            return False
    
    def _sanitize_log_data(self, data):
        """
        对日志中的敏感数据进行脱敏处理
        
        Args:
            data: 原始数据字典
            
        Returns:
            dict: 脱敏后的数据字典
        """
        if not isinstance(data, dict):
            return data
        
        sensitive_fields = ['password', 'token', 'credit_card', 'ssn', '身份证', '手机号']
        sanitized = {}
        
        for key, value in data.items():
            # 检查是否包含敏感字段
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                if isinstance(value, str) and len(value) > 4:
                    sanitized[key] = f"{value[:2]}****{value[-2:]}"
                else:
                    sanitized[key] = "****"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def log_performance_stats(self):
        """
        记录数据库性能统计信息
        """
        stats = self.get_pool_stats()
        logger.info(
            "数据库连接池性能统计",
            extra={
                'active_connections': stats['active_connections'],
                'total_connections': stats['total_connections'],
                'connection_errors': stats['connection_errors'],
                'max_pool_size': self.max_conn,
                'min_pool_size': self.min_conn,
                'pool_usage_percent': (stats['active_connections'] / self.max_conn * 100) if self.max_conn > 0 else 0
            }
        )
        return stats
    
    def execute_query(self, query, params=None, commit=False, query_name=None):
        """
        执行SQL查询
        
        Args:
            query: SQL查询语句
            params: 查询参数，可选
            commit: 是否提交事务
            query_name: 查询名称，用于日志记录，可选
            
        Returns:
            list: 查询结果列表（如果是SELECT语句）
        """
        start_time = time.time()
        query_type = query.strip().upper().split()[0] if query.strip() else 'UNKNOWN'
        
        try:
            with self.get_cursor(commit=commit) as cursor:
                cursor.execute(query, params or ())
                
                # 如果是SELECT语句，返回结果
                if query_type == 'SELECT':
                    result = cursor.fetchall()
                    execution_time = time.time() - start_time
                    logger.info(
                        "查询执行成功",
                        extra={
                            'query_type': query_type,
                            'query_name': query_name or 'unnamed',
                            'execution_time_ms': round(execution_time * 1000, 2),
                            'row_count': len(result)
                        }
                    )
                    return result
                
                execution_time = time.time() - start_time
                logger.info(
                    "非查询SQL执行成功",
                    extra={
                        'query_type': query_type,
                        'query_name': query_name or 'unnamed',
                        'execution_time_ms': round(execution_time * 1000, 2),
                        'affected_rows': cursor.rowcount
                    }
                )
                return cursor.rowcount
                
        except psycopg2.ProgrammingError as e:
            execution_time = time.time() - start_time
            error_msg = f"SQL编程错误: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'query_type': query_type,
                    'query_name': query_name or 'unnamed',
                    'execution_time_ms': round(execution_time * 1000, 2),
                    'error_type': 'ProgrammingError',
                    'query_snippet': query[:200] + ('...' if len(query) > 200 else '')
                }
            )
            raise QueryError(error_msg, error_code='DB_QUERY_001', original_error=e)
        
        except psycopg2.IntegrityError as e:
            execution_time = time.time() - start_time
            error_msg = f"数据完整性错误: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'query_type': query_type,
                    'query_name': query_name or 'unnamed',
                    'execution_time_ms': round(execution_time * 1000, 2),
                    'error_type': 'IntegrityError'
                }
            )
            raise QueryError(error_msg, error_code='DB_QUERY_002', original_error=e)
        
        except psycopg2.DataError as e:
            execution_time = time.time() - start_time
            error_msg = f"数据类型错误: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'query_type': query_type,
                    'query_name': query_name or 'unnamed',
                    'execution_time_ms': round(execution_time * 1000, 2),
                    'error_type': 'DataError'
                }
            )
            raise QueryError(error_msg, error_code='DB_QUERY_003', original_error=e)
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"查询执行失败: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'query_type': query_type,
                    'query_name': query_name or 'unnamed',
                    'execution_time_ms': round(execution_time * 1000, 2),
                    'error_type': type(e).__name__
                }
            )
            raise QueryError(error_msg, error_code='DB_QUERY_004', original_error=e)
    
    def fetch_one(self, query, params=None):
        """
        执行SQL查询并返回单行结果
        
        Args:
            query: SQL查询语句
            params: 查询参数，可选
            
        Returns:
            tuple: 查询结果的单行数据
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"查询单行数据失败: {str(e)}, Query: {query}, Params: {params}")
            raise
    
    def fetch_all(self, query, params=None):
        """
        执行SQL查询并返回所有结果
        
        Args:
            query: SQL查询语句
            params: 查询参数，可选
            
        Returns:
            list: 查询结果列表
        """
        return self.execute_query(query, params)
    
    def insert(self, table, data):
        """
        插入数据到指定表
        
        Args:
            table: 表名
            data: 字典，键为字段名，值为字段值
            
        Returns:
            int: 受影响的行数
        """
        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
            
            # 为敏感数据脱敏处理
            sanitized_data = self._sanitize_log_data(data)
            
            return self.execute_query(
                query,
                tuple(data.values()), 
                commit=True,
                query_name=f"insert_{table}"
            )
        except QueryError:
            raise
        except Exception as e:
            error_msg = f"数据插入失败: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'table': table,
                    'error_type': type(e).__name__
                }
            )
            raise TransactionError(error_msg, error_code='DB_TRANS_001', original_error=e)
    
    def update(self, table, data, condition, params=None):
        """
        更新指定表中的数据
        
        Args:
            table: 表名
            data: 字典，键为字段名，值为字段值
            condition: WHERE条件
            params: WHERE条件的参数，可选
            
        Returns:
            int: 受影响的行数
        """
        try:
            set_clause = ', '.join([f"{key} = %s" for key in data.keys()])
            query = f"UPDATE {table} SET {set_clause} WHERE {condition}"
            
            all_params = list(data.values())
            if params:
                all_params.extend(params)
            
            # 为敏感数据脱敏处理
            sanitized_data = self._sanitize_log_data(data)
            
            return self.execute_query(
                query,
                tuple(all_params), 
                commit=True,
                query_name=f"update_{table}"
            )
        except QueryError:
            raise
        except Exception as e:
            error_msg = f"数据更新失败: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'table': table,
                    'condition': condition,
                    'error_type': type(e).__name__
                }
            )
            raise TransactionError(error_msg, error_code='DB_TRANS_002', original_error=e)
    
    def delete(self, table, condition, params=None):
        """
        从指定表中删除数据
        
        Args:
            table: 表名
            condition: WHERE条件
            params: WHERE条件的参数，可选
            
        Returns:
            int: 受影响的行数
        """
        try:
            query = f"DELETE FROM {table} WHERE {condition}"
            return self.execute_query(
                query,
                params,
                commit=True,
                query_name=f"delete_{table}"
            )
        except QueryError:
            raise
        except Exception as e:
            error_msg = f"数据删除失败: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'table': table,
                    'condition': condition,
                    'error_type': type(e).__name__
                }
            )
            raise TransactionError(error_msg, error_code='DB_TRANS_003', original_error=e)
    
    def select(self, table, columns='*', condition=None, params=None, limit=None, offset=None):
        """
        从指定表中查询数据
        
        Args:
            table: 表名
            columns: 要查询的列，默认为所有列
            condition: WHERE条件，可选
            params: WHERE条件的参数，可选
            limit: 限制返回的行数，可选
            offset: 偏移量，可选
            
        Returns:
            list: 查询结果列表
        """
        query = f"SELECT {columns} FROM {table}"
        
        if condition:
            query += f" WHERE {condition}"
        
        if limit is not None:
            query += f" LIMIT {limit}"
        
        if offset is not None:
            query += f" OFFSET {offset}"
        
        return self.fetch_all(query, params)
    
    def create_table(self, table_name, columns):
        """
        创建表
        
        Args:
            table_name: 表名
            columns: 字典，键为列名，值为列定义
            
        Returns:
            bool: 是否创建成功
        """
        try:
            columns_def = ', '.join([f"{col} {definition}" for col, definition in columns.items()])
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_def})"
            
            self.execute_query(
                query,
                commit=True,
                query_name=f"create_table_{table_name}"
            )
            logger.info(
                "表创建成功",
                extra={
                    'table_name': table_name,
                    'column_count': len(columns)
                }
            )
            return True
        except Exception as e:
            error_msg = f"表创建失败: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'table_name': table_name,
                    'error_type': type(e).__name__
                }
            )
            raise QueryError(error_msg, error_code='DB_SCHEMA_001', original_error=e)

# 创建全局数据库管理器实例
db_manager = PostgreSQLManager()