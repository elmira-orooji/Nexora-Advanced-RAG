import type { AuthUser } from "../features/auth/types/auth";

export function canManageUsers(user: AuthUser | null | undefined) {
  return user?.role === "admin";
}

export function canManageKnowledge(user: AuthUser | null | undefined) {
  return user?.role === "admin";
}
