import { NextRequest, NextResponse } from "next/server";
import { isTokenExpired, refreshAccessToken } from "@/lib/auth";

async function shadowRequest(request: NextRequest, path: string) {
  const backendUrl = process.env.BACKEND_API_URL || "http://localhost:8001/api/v1";
  
  let accessToken = request.cookies.get("access_token")?.value;
  const refreshToken = request.cookies.get("refresh_token")?.value;
  const isProd = process.env.NODE_ENV === "production";
  
  let newCookieValue: string | null = null;

  // Check if token is expired and refresh if possible
  if (!accessToken || isTokenExpired(accessToken)) {
    if (refreshToken) {
      const newAccessToken = await refreshAccessToken(refreshToken);
      if (newAccessToken) {
        accessToken = newAccessToken;
        newCookieValue = newAccessToken;
      } else {
        const errRes = NextResponse.json({ detail: "انتهت صلاحية الجلسة، يرجى إعادة تسجيل الدخول" }, { status: 401 });
        errRes.cookies.delete("access_token");
        errRes.cookies.delete("refresh_token");
        return errRes;
      }
    } else {
      return NextResponse.json({ detail: "غير مصرح" }, { status: 401 });
    }
  }

  // Construct target URL
  const searchParams = request.nextUrl.search;
  const targetUrl = `${backendUrl}/${path}${searchParams}`;

  // Build headers
  const headers = new Headers();
  headers.set("Authorization", `Bearer ${accessToken}`);
  
  const contentType = request.headers.get("content-type");
  
  let body: BodyInit | null = null;
  if (request.method !== "GET" && request.method !== "HEAD") {
    if (contentType?.includes("multipart/form-data")) {
      // Forward form data (file upload)
      const formData = await request.formData();
      const forwardFormData = new FormData();
      formData.forEach((value, key) => {
        forwardFormData.append(key, value);
      });
      body = forwardFormData;
      // Do NOT set content-type header for multipart/form-data so fetch will generate boundary
    } else {
      body = await request.arrayBuffer();
      if (contentType) {
        headers.set("content-type", contentType);
      }
    }
  }

  try {
    const backendResponse = await fetch(targetUrl, {
      method: request.method,
      headers: headers,
      body: body,
      // For file upload progress or large files
      cache: "no-store",
    });

    // Check if backend responded with 401, maybe try refreshing one more time just in case
    if (backendResponse.status === 401 && refreshToken && !newCookieValue) {
      const secondChanceToken = await refreshAccessToken(refreshToken);
      if (secondChanceToken) {
        headers.set("Authorization", `Bearer ${secondChanceToken}`);
        newCookieValue = secondChanceToken;
        // Retry request
        const retryResponse = await fetch(targetUrl, {
          method: request.method,
          headers: headers,
          body: body,
          cache: "no-store",
        });
        return createResponse(retryResponse, newCookieValue, isProd);
      }
    }

    return createResponse(backendResponse, newCookieValue, isProd);
  } catch (error) {
    console.error(`Proxy error for ${request.method} ${path}:`, error);
    return NextResponse.json(
      { detail: "خطأ في الاتصال بالخادم الخلفي" },
      { status: 502 }
    );
  }
}

async function createResponse(backendResponse: Response, newCookieValue: string | null, isProd: boolean) {
  // Read backend body
  const data = await backendResponse.arrayBuffer();
  
  // Set up response
  const responseHeaders = new Headers();
  const backendContentType = backendResponse.headers.get("content-type");
  if (backendContentType) {
    responseHeaders.set("content-type", backendContentType);
  }

  const res = new NextResponse(data, {
    status: backendResponse.status,
    statusText: backendResponse.statusText,
    headers: responseHeaders,
  });

  // If a new access token was generated, update the cookie in client response
  if (newCookieValue) {
    res.cookies.set({
      name: "access_token",
      value: newCookieValue,
      httpOnly: true,
      secure: isProd,
      sameSite: "strict",
      path: "/",
      maxAge: 3600,
    });
  }

  return res;
}

export async function GET(request: NextRequest, { params }: { params: { path: string[] } }) {
  return shadowRequest(request, params.path.join("/"));
}

export async function POST(request: NextRequest, { params }: { params: { path: string[] } }) {
  return shadowRequest(request, params.path.join("/"));
}

export async function PUT(request: NextRequest, { params }: { params: { path: string[] } }) {
  return shadowRequest(request, params.path.join("/"));
}

export async function DELETE(request: NextRequest, { params }: { params: { path: string[] } }) {
  return shadowRequest(request, params.path.join("/"));
}

export async function PATCH(request: NextRequest, { params }: { params: { path: string[] } }) {
  return shadowRequest(request, params.path.join("/"));
}
