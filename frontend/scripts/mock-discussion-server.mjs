import http from "node:http";
import { pathToFileURL } from "node:url";

const CORES = ["MELCHIOR-1", "BALTHASAR-2", "CASPER-3"];

const COMPLETE_DISCUSSION = [
  { type: "phase", phase: "OPENING", active_cores: CORES },
  {
    type: "act",
    id: 1,
    round: 0,
    act: {
      core: "MELCHIOR-1",
      kind: "POSITION",
      content: "The proposal is technically viable if the rollback criteria are explicit.",
      reply_to: null,
    },
  },
  {
    type: "act",
    id: 2,
    round: 0,
    act: {
      core: "BALTHASAR-2",
      kind: "POSITION",
      content: "The affected group needs advance notice and a clear route to request review.",
      reply_to: null,
    },
  },
  {
    type: "act",
    id: 3,
    round: 0,
    act: {
      core: "CASPER-3",
      kind: "CHALLENGE",
      content: "The stated safeguards do not remove the incentive to expand the trial prematurely.",
      reply_to: null,
    },
  },
  { type: "phase", phase: "DISCUSSION", active_cores: CORES },
  {
    type: "act",
    id: 4,
    round: 1,
    act: {
      core: "MELCHIOR-1",
      kind: "RESPONSE",
      content: "Limit the trial to one cycle and require a measurable rollback threshold.",
      reply_to: 3,
    },
  },
  {
    type: "act",
    id: 5,
    round: 1,
    act: {
      core: "BALTHASAR-2",
      kind: "PROPOSE_CONDITION",
      content: "Publish the review and retain a human appeal path throughout the trial.",
      reply_to: 1,
    },
  },
  {
    type: "act",
    id: 6,
    round: 1,
    act: {
      core: "CASPER-3",
      kind: "PASS",
      content: "The new conditions clarify the risk, but I still oppose proceeding now.",
      reply_to: 5,
    },
  },
  { type: "phase", phase: "BALLOTING", active_cores: [] },
  { type: "ballots_locked" },
  {
    type: "result",
    outcome: "APPROVED_WITH_CONDITIONS",
    ballots: [
      {
        core: "MELCHIOR-1",
        vote: "AGREE",
        confidence: 0.82,
        rationale: "The bounded trial and rollback threshold make the proposal testable.",
        conditions: [],
      },
      {
        core: "BALTHASAR-2",
        vote: "CONDITIONAL",
        confidence: 0.76,
        rationale: "Proceed only with notice, published review, and a human appeal route.",
        conditions: ["Publish the review.", "Retain a human appeal path."],
      },
      {
        core: "CASPER-3",
        vote: "DISAGREE",
        confidence: 0.69,
        rationale: "The incentive to expand the trial remains stronger than the safeguards.",
        conditions: [],
      },
    ],
    conditions: ["Publish the review.", "Retain a human appeal path."],
    disclaimer: "Decision support only. No real-world action was executed.",
  },
];

function pause(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export function eventsForMotion(question) {
  return String(question).includes("[fail]")
    ? [{ type: "error", message: "Mock deliberation failed safely." }]
    : COMPLETE_DISCUSSION;
}

async function readMotion(request) {
  let body = "";
  for await (const chunk of request) {
    body += chunk;
    if (body.length > 20_000) throw new Error("request too large");
  }
  return JSON.parse(body);
}

export function createMockDiscussionServer({ delayMs = 140 } = {}) {
  return http.createServer(async (request, response) => {
    if (request.method !== "POST" || request.url !== "/api/discuss") {
      response.writeHead(404).end();
      return;
    }

    let motion;
    try {
      motion = await readMotion(request);
    } catch {
      response.writeHead(400, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ detail: "Invalid motion." }));
      return;
    }

    response.writeHead(200, {
      "Content-Type": "application/x-ndjson",
      "Cache-Control": "no-store",
    });

    const events = eventsForMotion(motion.question);

    for (const event of events) {
      if (response.destroyed) break;
      response.write(`${JSON.stringify(event)}\n`);
      if (delayMs > 0) await pause(delayMs);
    }
    response.end();
  });
}

const invokedDirectly = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (invokedDirectly) {
  const server = createMockDiscussionServer();
  server.listen(8000, "127.0.0.1", () => {
    console.log("Mock MAGI discussion server listening at http://127.0.0.1:8000");
  });
  process.on("SIGINT", () => server.close(() => process.exit(0)));
}

export { COMPLETE_DISCUSSION };
