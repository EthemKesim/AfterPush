import express from "express";

const app = express();

const PORT = process.env.PORT || 3000;

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
    version: "1.0.0"
  });
});

app.get("/test/cpu", (_req, res) => {
  const end = Date.now() + 5000;

  while (Date.now() < end) {
    Math.sqrt(Math.random());
  }

  res.json({
    message: "CPU load test completed"
  });
});

app.listen(PORT, () => {
  console.log(`AfterPush API running on port ${PORT}`);
});