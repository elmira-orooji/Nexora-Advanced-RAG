export type UserRole = "admin" | "user";

export interface AuthUser {
  id: string;
  username: string;
  role: UserRole;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
}

export interface AuthSession {
  expiresAt: number;
  user: AuthUser;
}

export interface LoginResponse {
  expires_in: number;
  user: AuthUser;
}
