export interface DecodedToken {
  sub: string; // user_id
  tenant_id: string;
  role: string;
  exp: number;
}

export function decodeToken(token: string): DecodedToken | null {
  try {
    const payloadBase64 = token.split(".")[1];
    const payloadJson = Buffer.from(payloadBase64, "base64").toString("utf-8");
    return JSON.parse(payloadJson);
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const decoded = decodeToken(token);
  if (!decoded) return true;
  // Current time in seconds. Add a 10-second buffer.
  const now = Math.floor(Date.now() / 1000);
  return decoded.exp < now + 10;
}

export async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  try {
    const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8001/api/v1";
    const response = await fetch(`${backendUrl}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      return null;
    }

    const data = await response.json(); // { access_token, token_type }
    return data.access_token;
  } catch (error) {
    console.error("Token refresh failed:", error);
    return null;
  }
}
