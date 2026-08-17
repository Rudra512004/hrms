# RBAC Rules

CRITICAL: Dynamic Role-Based Access Control (RBAC)

1. Super Admin must be able to dynamically:
   - Create and modify roles.
   - Assign permissions to roles.
   - Assign roles to users.
   - Grant additional individual permissions.
   - Set expiry dates for temporary privileges.
   - Revoke privileges.
   - Audit privilege changes.

2. NEVER hardcode role names (e.g., HR, Manager, Employee) into authorization logic.
3. All authorization must be permission-based, checked at the endpoint/view level.
