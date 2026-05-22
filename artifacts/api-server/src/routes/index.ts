import { Router, type IRouter } from "express";
import healthRouter from "./health";
import authRouter from "./auth";
import v1ProxyRouter from "./v1proxy";

const router: IRouter = Router();

router.use(healthRouter);
router.use(authRouter);
router.use("/v1", v1ProxyRouter);

export default router;
