import http, { Response } from "k6/http";
import { check } from "k6";
import { SharedArray } from "k6/data";
import type { Options, Scenario } from "k6/options";


const BASE_URL: string = __ENV.BASE_URL || "http://localhost:8000";
const RATES: number[] = (__ENV.RATES || "0.5,1,2,3").split(",").map(Number);
const STAGE_SECONDS: number = Number(__ENV.STAGE_SECONDS || 60);
const GAP_SECONDS = 10;

const bodies: string[] = new SharedArray("bodies", (): string[] => JSON.parse(open("./users.json")));

const scenarios: Record<string, Scenario> = {};
const thresholds: Record<string, string[]> = {};

RATES.forEach((rate: number, i: number) => {
  scenarios[`rate_${String(rate).replace(".", "_")}`] = {
    executor: "constant-arrival-rate",
    rate: rate * 10,
    timeUnit: "10s",
    duration: `${STAGE_SECONDS}s`,
    startTime: `${i * (STAGE_SECONDS + GAP_SECONDS)}s`,
    preAllocatedVUs: 20,
    maxVUs: 200,
    tags: { rate: String(rate) },
  };
  thresholds[`http_req_duration{rate:${rate}}`] = ["max>=0"];
  thresholds[`http_req_failed{rate:${rate}}`] = ["rate>=0"];
});

export const options: Options = {
  scenarios,
  thresholds,
  summaryTrendStats: ["med", "p(95)", "p(99)", "max"],
};

export default function (): void {
  const body = bodies[Math.floor(Math.random() * bodies.length)];
  const res = http.post(`${BASE_URL}/predict`, body, {
    headers: { "Content-Type": "application/json" },
  });
  check(res, { "status 200": (r: Response) => r.status === 200 });
}
