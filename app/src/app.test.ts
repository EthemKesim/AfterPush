import request from "supertest";
import { describe, expect, it } from "vitest";

import app from "./app.js";

describe("AfterPush API", () => {
  it("GET / returns service information", async () => {
    const response = await request(app).get("/");

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      service: "afterpush-api",
      message: "AfterPush API is running"
    });
  });

  it("GET /health returns a healthy response", async () => {
    const response = await request(app).get("/health");

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      status: "healthy"
    });
  });

  it("GET /version returns the application version", async () => {
    const response = await request(app).get("/version");

    expect(response.status).toBe(200);
    expect(response.body).toEqual({
      service: "afterpush-api",
      version: "1.0.0"
    });
  });
});