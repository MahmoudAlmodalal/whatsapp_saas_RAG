import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const { email, password } = await request.json();

    const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8001/api/v1";
    
    // Call the backend FastAPI login endpoint
    const response = await fetch(`${backendUrl}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: "فشل تسجيل الدخول" }));
      return NextResponse.json(
        { detail: errorData.detail || "البريد الإلكتروني أو كلمة المرور غير صحيحة" },
        { status: response.status }
      );
    }

    const tokenData = await response.json(); // { access_token, refresh_token, token_type }

    // Decode token to get user info (role, tenant_id, sub/user_id)
    let user = null;
    try {
      const payloadBase64 = tokenData.access_token.split(".")[1];
      const payloadJson = Buffer.from(payloadBase64, "base64").toString("utf-8");
      const payload = JSON.parse(payloadJson);
      user = {
        id: payload.sub,
        tenant_id: payload.tenant_id,
        role: payload.role,
        email: email,
      };
    } catch (e) {
      console.error("Error decoding access token:", e);
    }

    const isProd = process.env.NODE_ENV === "production";
    const res = NextResponse.json({ success: true, user });

    // Set HTTP-Only cookies
    res.cookies.set({
      name: "access_token",
      value: tokenData.access_token,
      httpOnly: true,
      secure: isProd,
      sameSite: "strict",
      path: "/",
      maxAge: 3600, // 1 hour
    });

    res.cookies.set({
      name: "refresh_token",
      value: tokenData.refresh_token,
      httpOnly: true,
      secure: isProd,
      sameSite: "strict",
      path: "/",
      maxAge: 7 * 24 * 3600, // 7 days
    });

    return res;
  } catch (error) {
    console.error("Login proxy error:", error);
    return NextResponse.json(
      { detail: "حدث خطأ أثناء الاتصال بالخادم. يرجى المحاولة لاحقاً." },
      { status: 500 }
    );
  }
}
