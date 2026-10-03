import express from "express";
import {
  httpRequestDurationSeconds,
  httpRequestsTotal,
  register,
} from "./metrics.js";

const app = express();

app.use(express.json());

// Her HTTP request için metric toplar.
// /metrics'i hariç tutuyoruz çünkü Prometheus'un kendi scrape
// isteklerinin uygulama trafiğini şişirmesini istemiyoruz.
app.use((req, res, next) => {
  if (req.path === "/metrics") {
    next();
    return;
  }

  const end = httpRequestDurationSeconds.startTimer();

  res.on("finish", () => {
    const route = req.route?.path ?? "unknown";

    const labels = {
      method: req.method,
      route,
      status_code: res.statusCode.toString(),
    };

    // Toplam request sayısını artır.
    httpRequestsTotal.inc(labels);

    // Request'in ne kadar sürdüğünü Histogram'a kaydet.
    end(labels);
  });

  next();
});

app.get("/", (_req, res) => {
  res.json({
    service: "afterpush-api",
    message: "AfterPush API is running",
  });
});

app.get("/health", (_req, res) => {
  res.status(200).json({
    status: "healthy",
  });
});

app.get("/version", (_req, res) => {
  res.json({
    service: "afterpush-api",
    version: "1.2.0",
  });
});

// Prometheus bu endpoint'i scrape edecek.
app.get("/metrics", async (_req, res) => {
  res.set("Content-Type", register.contentType);
  res.end(await register.metrics());
});

export default app;