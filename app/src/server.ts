import express from "express";



const app = express();

const PORT = process.env.PORT || 3000;
const branchProtectionTest: number = "intentional-failure";

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

app.listen(PORT, () => {
  console.log(`AfterPush API running on port ${PORT}`);
});