/**
 * Dynamic RBAC Architecture
 * 
 * The eventual authorization model uses granular permissions.
 * DO NOT hardcode checks like `if (role === 'HR')`.
 */

/**
 * Checks if the current authenticated user has a specific permission.
 * Examples: 'employee.view', 'attendance.view', 'leave.approve'
 * 
 * Note: This is currently a stub until DEV1 provides the backend API
 * for fetching user permissions.
 * 
 * @param permission The permission string to check
 * @returns boolean
 */
export const hasPermission = (permission: string): boolean => {
  console.warn(`hasPermission check for '${permission}' returning true as a placeholder. Waiting for backend API.`);
  
  // TODO: Read from actual user permissions state (e.g., Context/Redux)
  return true; 
};
