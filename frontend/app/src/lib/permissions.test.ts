import { describe, expect, it } from "vitest";
import type { AuthUser } from "../features/auth/types/auth";
import { canManageKnowledge, canManageUsers } from "./permissions";

const makeUser = (role: AuthUser["role"]): AuthUser => ({
  id: "user-1",
  username: role,
  role,
  organization_id: "org-1",
  organization_name: "Nexora",
  organization_slug: "nexora",
});

describe("canManageUsers", () => {
  it("allows administrators", () => expect(canManageUsers(makeUser("admin"))).toBe(true));
  it("rejects regular and anonymous users", () => {
    expect(canManageUsers(makeUser("user"))).toBe(false);
    expect(canManageUsers(null)).toBe(false);
  });
});

describe("canManageKnowledge", () => {
  it("allows administrators", () => expect(canManageKnowledge(makeUser("admin"))).toBe(true));
  it("rejects regular and anonymous users", () => {
    expect(canManageKnowledge(makeUser("user"))).toBe(false);
    expect(canManageKnowledge(null)).toBe(false);
  });
});
