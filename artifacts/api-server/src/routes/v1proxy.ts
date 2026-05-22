import { Router } from "express";
import type { Request, Response } from "express";

const router = Router();

const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8000/api/v1";

router.all("/*path", async (req: Request, res: Response) => {
  const targetPath = req.path;
  const queryString = req.url.includes("?") ? req.url.slice(req.url.indexOf("?")) : "";
  const targetUrl = `${BACKEND_API_URL}${targetPath}${queryString}`;

  const accessToken = req.cookies?.access_token;

  const headers: Record<string, string> = {
    "Content-Type": req.headers["content-type"] || "application/json",
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const fetchInit: RequestInit = {
    method: req.method,
    headers,
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    const isMultipart = (req.headers["content-type"] || "").includes("multipart/form-data");
    if (!isMultipart) {
      fetchInit.body = JSON.stringify(req.body);
    }
  }

  try {
    const response = await fetch(targetUrl, fetchInit);
    const contentType = response.headers.get("content-type") || "application/json";
    res.status(response.status).setHeader("Content-Type", contentType);

    if (contentType.includes("application/json")) {
      const data = await response.json();
      return res.json(data);
    } else {
      const buffer = await response.arrayBuffer();
      return res.send(Buffer.from(buffer));
    }
  } catch (err) {
    req.log.error({ err, targetUrl }, "Backend proxy error");
    return res.status(502).json({ detail: "تعذر الوصول إلى الخادم الخلفي. يرجى المحاولة لاحقاً." });
  }
});

export default router;
