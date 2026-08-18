/**
 * Pending DEV1 API Contract:
 * Do NOT invent endpoint URLs.
 * Do NOT call nonexistent APIs.
 * Do NOT fake successful authentication.
 * 
 * This file serves as the architectural abstraction for authentication.
 * It will be implemented once the official API documentation is provided.
 */

export interface User {
  id: string;
  hrmsId?: string; // Assigned later in the identity lifecycle
  email: string;
  firstName: string;
  lastName: string;
}

export const authService = {
  /**
   * Log in using company email and password.
   */
  login: async (_email: string, _password: string): Promise<void> => {
    // TODO: Implement API call
  },

  /**
   * Activate an account and set a password.
   */
  activate: async (_uid: string, _token: string, _password: string): Promise<void> => {
    // TODO: Implement API call
  },



  /**
   * Log out the current user.
   */
  logout: async (): Promise<void> => {
    // TODO: Implement API call
  },

  /**
   * Fetch the currently authenticated user session.
   */
  getCurrentUser: async (): Promise<User | null> => {
    return null;
  }
};
