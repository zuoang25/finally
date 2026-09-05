import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import http from "node:http";
import { promisify } from "node:util";

const exec = promisify(execFile);

const CONTAINER = process.env.E2E_APP_CONTAINER ?? "finally-e2e-app";
const DOCKER_SOCKET = "/var/run/docker.sock";

/**
 * Forces a genuine disconnect of the live SSE stream by restarting the app container.
 *
 * `BrowserContext.setOffline()` is not enough: Chromium's offline emulation blocks new
 * requests but leaves an already-streaming response alone, so the EventSource keeps
 * ticking and nothing is actually tested. Bouncing the server is the real thing — the
 * socket dies under the browser and EventSource's own retry has to bring it back.
 *
 * Works both from the host (`docker` CLI) and from inside the compose `playwright`
 * service (Docker Engine API over the mounted unix socket).
 */
export async function restartAppContainer(): Promise<void> {
  if (existsSync(DOCKER_SOCKET)) {
    await restartViaSocket();
    return;
  }
  await exec("docker", ["restart", "--time", "5", CONTAINER]);
}

/** Whether a forced-disconnect test can run in this environment. */
export async function canRestartApp(): Promise<boolean> {
  if (existsSync(DOCKER_SOCKET)) return true;
  try {
    await exec("docker", ["inspect", "--format", "{{.State.Status}}", CONTAINER]);
    return true;
  } catch {
    return false;
  }
}

function restartViaSocket(): Promise<void> {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        socketPath: DOCKER_SOCKET,
        path: `/containers/${CONTAINER}/restart?t=5`,
        method: "POST",
      },
      (res) => {
        res.resume();
        res.on("end", () =>
          res.statusCode && res.statusCode < 400
            ? resolve()
            : reject(new Error(`docker restart failed: HTTP ${res.statusCode}`)),
        );
      },
    );
    req.on("error", reject);
    req.end();
  });
}
