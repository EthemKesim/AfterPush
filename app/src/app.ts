import express from "express";

const app = express();

app.use(express.json());

app.get("/", (_req, res) => {
  res.json({
    service: "afterpush-api",
    message: "AfterPush API is running"
  });
});

app.get("/health", (_req, res) => {
  res.status(200).json({
    status: "healthy"
  });
});

app.get("/version", (_req, res) => {
  res.json({
    service: "afterpush-api",
    version: "1.1.0"
  });
});

export default app;