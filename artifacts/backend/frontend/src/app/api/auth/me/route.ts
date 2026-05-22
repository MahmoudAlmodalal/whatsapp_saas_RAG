import { NextRequest, NextResponse } from "next/server";
import { decodeToken, isTokenExpired, refreshAccessToken } from "@/lib/auth";

export async function GET(request: NextRequest) {
  let accessToken = request.cookies.get("access_token")?.value;
  const refreshToken = request.cookies.get("refresh_token")?.value;

  const isProd = process.env.NODE_ENV === "production";

  if (!accessToken || isTokenExpired(accessToken)) {
    if (refreshToken) {
      // Attempt to refresh access token
      const newAccessToken = await refreshAccessToken(refreshToken);
      if (newAccessToken) {
        accessToken = newAccessToken;
      } else {
        // Refresh token invalid or expired
        const errResponse = NextResponse.json({ detail: "غير مصرح" }, { status: 401 });
        errResponse.cookies.delete("access_token");
        errResponse.cookies.delete("refresh_token");
        return errResponse;
      }
    } else {
      return NextResponse.json({ detail: "غير مصرح" }, { status: 401 });
    }
  }

  const decoded = decodeToken(accessToken);
  if (!decoded) {
    return NextResponse.json({ detail: "غير مصرح" }, { status: 401 });
  }

  const user = {
    id: decoded.sub,
    tenant_id: decoded.tenant_id,
    role: decoded.role,
  };

  const response = NextResponse.json({ authenticated: true, user });

  // If a new access token was generated, update the cookie
  if (accessToken !== request.cookies.get("access_token")?.value) {
    response.cookies.set({
      name: "access_token",
      value: accessToken,
      httpOnly: true,
      secure: isProd,
      sameSite: "strict",
      path: "/",
      maxAge: 3600,
    });
  }

  return response;
}
