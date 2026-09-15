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
  res.status(500).json({
    status: "unhealthy"
  });
});
app.get("/version", (_req, res) => {
  res.json({
    service: "afterpush-api",
    version: "1.0.0"
  });
});

app.listen(PORT, () => {
  console.log(`AfterPush API running on port ${PORT}`);
});