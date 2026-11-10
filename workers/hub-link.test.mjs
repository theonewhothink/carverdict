// Regression test: a password set on an unverified email must not survive the verified owner's
// Google or Apple sign-in (account pre-hijack). Drives HubDO.dispatch on an in-memory SQLite store.
import { test } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { HubDO } from "./hub.js";

function hub() {
  const db = new DatabaseSync(":memory:");
  const sql = { exec(q, ...a) { const s = db.prepare(q); const rows = s.columns().length ? s.all(...a) : (s.run(...a), []); return { toArray: () => rows }; } };
  const h = new HubDO({ storage: { sql } });
  return (op, body) => h.dispatch(op, body, {});
}

test("provider sign-in removes a password and sessions set before email ownership was proven", async () => {
  const call = hub();
  const email = "owner@example.test";
  const early = await call("signup", { email, password: "stranger-pass-1", ip: "203.0.113.9" });
  const owner = await call("oauth", { email, name: "Owner", sub: "g-1", provider: "google" });
  assert.equal(owner.user.id, early.user.id);
  await assert.rejects(call("login", { email, password: "stranger-pass-1", ip: "203.0.113.9" }));
  const old = await call("me", { token: early.token }).catch(() => ({ user: null }));
  assert.equal(old.user, null);
  const mine = await call("me", { token: owner.token });
  assert.equal(mine.user.id, owner.user.id);
});
