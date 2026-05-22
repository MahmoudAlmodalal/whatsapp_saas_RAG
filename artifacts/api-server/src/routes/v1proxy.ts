import { Router } from "express";
import type { Request, Response } from "express";

const router = Router();

const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:9000/api/v1";

router.all("/*path", async (req: Request, res: Response) => {
  const targetPath = req.path;
  const queryString = req.url.includes("?") ? req.url.slice(req.url.indexOf("?")) : "";
  const targetUrl = `${BACKEND_API_URL}${targetPath}${queryString}`;

  const accessToken = req.cookies?.access_token;
  const contentType = req.headers["content-type"] || "";
  const isMultipart = contentType.includes("multipart/form-data");

  const headers: Record<string, string> = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const fetchInit: RequestInit = {
    method: req.method,
    headers,
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    if (isMultipart) {
      // Pass the raw request stream for multipart uploads (body not parsed by Express)
      // Copy content-type including the boundary parameter
      headers["Content-Type"] = contentType;
      // Node.js IncomingMessage is a Readable stream compatible with fetch body
      fetchInit.body = req as unknown as ReadableStream;
      // @ts-expect-error Node.js fetch accepts Node streams
      fetchInit.duplex = "half";
    } else {
      headers["Content-Type"] = "application/json";
      fetchInit.body = JSON.stringify(req.body);
    }
  }

  try {
    const response = await fetch(targetUrl, fetchInit);
    const resContentType = response.headers.get("content-type") || "application/json";
    res.status(response.status).setHeader("Content-Type", resContentType);

    if (resContentType.includes("application/json")) {
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
