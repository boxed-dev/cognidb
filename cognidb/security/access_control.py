"""Access control and permissions management."""

from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field
from enum import Enum, auto
from ..core.exceptions import SecurityError


class Permission(Enum):
    """Database permissions."""
    SELECT = auto()
    INSERT = auto()
    UPDATE = auto()
    DELETE = auto()
    CREATE = auto()
    DROP = auto()
    ALTER = auto()
    EXECUTE = auto()


@dataclass
class TablePermissions:
    """Permissions for a specific table."""
    table_name: str
    allowed_operations: Set[Permission] = field(default_factory=set)
    allowed_columns: Optional[Set[str]] = None  # None means all columns
    row_filter: Optional[str] = None  # SQL condition for row-level security
    
    def can_access_column(self, column: str) -> bool:
        """Check if column access is allowed."""
        if self.allowed_columns is None:
            return True
        return column in self.allowed_columns
    
    def can_perform_operation(self, operation: Permission) -> bool:
        """Check if operation is allowed."""
        return operation in self.allowed_operations


@dataclass
class UserPermissions:
    """User's database permissions."""
    user_id: str
    is_admin: bool = False
    table_permissions: Dict[str, TablePermissions] = field(default_factory=dict)
    global_permissions: Set[Permission] = field(default_factory=set)
    max_rows_per_query: int = 10000
    max_execution_time: int = 30  # seconds
    allowed_schemas: Set[str] = field(default_factory=set)
    
    def add_table_permission(self, table_perm: TablePermissions):
        """Add permissions for a table."""
        self.table_permissions[table_perm.table_name] = table_perm
    
    def can_access_table(self, table: str) -> bool:
        """Check if user can access table."""
        if self.is_admin:
            return True
        return table in self.table_permissions
    
    def can_perform_operation_on_table(self, table: str, operation: Permission) -> bool:
        """Check if user can perform operation on table."""
        if self.is_admin:
            return True
        if table not in self.table_permissions:
            return False
        return self.table_permissions[table].can_perform_operation(operation)


class AccessController:
    """
    Controls access to database resources.
    
    Implements:
    - Table-level permissions
    - Column-level permissions
    - Row-level security
    - Operation restrictions
    - Resource limits
    """
    
    def __init__(self):
        """Initialize access controller."""
        self.users: Dict[str, UserPermissions] = {}
        self.default_permissions = UserPermissions(
            user_id="default",
            global_permissions={Permission.SELECT},
            max_rows_per_query=1000,
            max_execution_time=10
        )
    
    def add_user(self, user_permissions: UserPermissions):
        """Add user with permissions."""
        self.users[user_permissions.user_id] = user_permissions
    
    def get_user_permissions(self, user_id: str) -> UserPermissions:
        """Get user permissions or default if not found."""
        return self.users.get(user_id, self.default_permissions)
    
    def check_table_access(self, user_id: str, tables: List[str]) -> None:
        """
        Check if user can access all tables.
        
        Raises:
            SecurityError: If access denied
        """
        permissions = self.get_user_permissions(user_id)
        
        for table in tables:
            if not permissions.can_access_table(table):
                raise SecurityError(f"Access denied to table: {table}")
    
    def check_column_access(self, user_id: str, table: str, columns: List[str]) -> None:
        """
        Check if user can access columns.
        
        Raises:
            SecurityError: If access denied
        """
        permissions = self.get_user_permissions(user_id)
        
        if not permissions.can_access_table(table):
            raise SecurityError(f"Access denied to table: {table}")
        
        if permissions.is_admin:
            return
        
        if table in permissions.table_permissions:
            table_perm = permissions.table_permissions[table]
            for column in columns:
                if not table_perm.can_access_column(column):
                    raise SecurityError(f"Access denied to column: {table}.{column}")
    
    def check_operation(self, user_id: str, operation: Permission, tables: List[str]) -> None:
        """
        Check if user can perform operation.
        
        Raises:
            SecurityError: If operation not allowed
        """
        permissions = self.get_user_permissions(user_id)
        
        # Check global permissions first
        if operation in permissions.global_permissions:
            return
        
        # Check table-specific permissions
        for table in tables:
            if not permissions.can_perform_operation_on_table(table, operation):
                raise SecurityError(
                    f"Operation {operation.name} not allowed on table: {table}"
                )
    
    def get_row_filters(self, user_id: str, table: str) -> Optional[str]:
        """Get row-level security filters for table."""
        permissions = self.get_user_permissions(user_id)
        
        if permissions.is_admin:
            return None
        
        if table in permissions.table_permissions:
            return permissions.table_permissions[table].row_filter
        
        return None
    
    def get_resource_limits(self, user_id: str) -> Dict[str, int]:
        """Get resource limits for user."""
        permissions = self.get_user_permissions(user_id)
        
        return {
            'max_rows': permissions.max_rows_per_query,
            'max_execution_time': permissions.max_execution_time
        }
    
    def create_read_only_user(self, user_id: str, allowed_tables: List[str]) -> UserPermissions:
        """Create a read-only user with access to specific tables."""
        user = UserPermissions(
            user_id=user_id,
            global_permissions={Permission.SELECT},
            max_rows_per_query=5000,
            max_execution_time=20
        )
        
        for table in allowed_tables:
            user.add_table_permission(
                TablePermissions(
                    table_name=table,
                    allowed_operations={Permission.SELECT}
                )
            )
        
        self.add_user(user)
        return user
    
    def create_restricted_user(self, 
                             user_id: str,
                             table_permissions_dict: Dict[str, Dict[str, Any]]) -> UserPermissions:
        """
        Create user with specific table permissions.
        
        Args:
            user_id: User identifier
            table_permissions_dict: Dictionary of table permissions
                {
                    'users': {
                        'operations': ['SELECT'],
                        'columns': ['id', 'name', 'email'],
                        'row_filter': "department = 'sales'"
                    }
                }
        """
        user = UserPermissions(user_id=user_id)
        
        for table, perms in table_permissions_dict.items():
            operations = {
                Permission[op] for op in perms.get('operations', ['SELECT'])
            }
            
            table_perm = TablePermissions(
                table_name=table,
                allowed_operations=operations,
                allowed_columns=set(perms['columns']) if 'columns' in perms else None,
                row_filter=perms.get('row_filter')
            )
            
            user.add_table_permission(table_perm)
        
        self.add_user(user)
        return user