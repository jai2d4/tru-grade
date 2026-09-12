/**
 * Typed client for the Phase 21 accounts endpoints (app/routers/auth.py).
 * Identity travels as an httpOnly session cookie set by the backend on
 * signup/login — nothing here stores a token client-side.
 */
import { json, request } from "./client";
import type { CurrentUser, LoginRequest, SignupRequest } from "./types";

export const auth = {
  signup(body: SignupRequest): Promise<CurrentUser> {
    return request<CurrentUser>("/api/v1/auth/signup", json(body, "POST"));
  },
  login(body: LoginRequest): Promise<CurrentUser> {
    return request<CurrentUser>("/api/v1/auth/login", json(body, "POST"));
  },
  logout(): Promise<void> {
    return request<void>("/api/v1/auth/logout", { method: "POST" });
  },
  me(): Promise<CurrentUser> {
    return request<CurrentUser>("/api/v1/auth/me");
  },
};
