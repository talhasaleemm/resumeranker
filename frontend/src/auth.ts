import NextAuth, { type DefaultSession } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { User } from "next-auth";

interface AppUser extends User {
  accessToken?: string;
}

/**
 * Safely extract the backend access token from the login response.
 * The FastAPI Token schema returns `access_token` (snake_case), but we
 * defensively accept `accessToken` (camelCase) as well so a payload-shape
 * drift can never crash the authorize callback.
 */
function extractAccessToken(data: unknown): string | undefined {
  if (!data || typeof data !== "object") return undefined;
  const d = data as Record<string, unknown>;
  const token = d.access_token ?? d.accessToken;
  return typeof token === "string" && token.length > 0 ? token : undefined;
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials): Promise<AppUser | null> {
        // `credentials` may be undefined during certain lifecycle hooks.
        const email = credentials?.email;
        const password = credentials?.password;
        if (!email || !password) {
          return null;
        }

        try {
          const res = await fetch(
            "http://127.0.0.1:8001/api/v1/auth/login",
            {
              method: "POST",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: new URLSearchParams({
                username: String(email),
                password: String(password),
              }).toString(),
            }
          );

          // Non-2xx (e.g. 401 bad creds) must return null, never throw.
          if (!res.ok) {
            return null;
          }

          const data = await res.json().catch(() => null);
          const accessToken = extractAccessToken(data);

          // Even without a token we deny login rather than crash the loop.
          if (!accessToken) {
            return null;
          }

          return {
            id: String(email),
            email: String(email),
            accessToken,
          };
        } catch {
          // Network/DNS failure talking to the backend: fail closed, cleanly.
          return null;
        }
      },
    }),
  ],
  // Required for non-Vercel/local hosts (localhost, 127.0.0.1, LAN IPs) so
  // Auth.js trusts the incoming Host header and validates CSRF correctly.
  // Without this, the credentials callback fails CSRF validation BEFORE
  // `authorize()` runs, producing zero backend traffic + "Failed to fetch".
  trustHost: true,
  pages: {
    signIn: "/",
  },
  callbacks: {
    async jwt({ token, user }) {
      // `user` is only present on the initial sign-in; guard against undefined.
      if (user && "accessToken" in user) {
        const t = (user as AppUser).accessToken;
        if (typeof t === "string" && t.length > 0) {
          token.accessToken = t;
        }
      }
      return token;
    },
    async session({ session, token }) {
      const t = token?.accessToken;
      session.accessToken = typeof t === "string" ? t : undefined;
      return session;
    },
  },
  session: {
    strategy: "jwt",
  },
});
