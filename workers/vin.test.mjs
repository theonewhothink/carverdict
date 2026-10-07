import { test } from "node:test";
import assert from "node:assert/strict";
import { inspectVin, normalizeVin, severeRecall, validVin } from "./vin.mjs";

test("VIN input is normalized without accepting forbidden letters", () => {
  assert.equal(normalizeVin(" 1hg-cm82633a004352 "), "1HGCM82633A004352");
  assert.equal(validVin("1HGCM82633A004352"), true);
  assert.equal(validVin("1HGCM82633A00435"), false);
  assert.equal(validVin("1HGCM82633A00O352"), false);
});

test("safety-critical recall language is flagged", () => {
  assert.equal(severeRecall({ Component: "SERVICE BRAKES", Summary: "" }), true);
  assert.equal(severeRecall({ Component: "EQUIPMENT", Summary: "label may detach" }), false);
  assert.equal(severeRecall({ Component: "ENGINE", Consequence: "may stall and cause a crash" }), true);
});

test("inspection joins decoded vehicle details to recall results", async () => {
  const responses = [
    { Results: [{ ModelYear: "2003", Make: "HONDA", Model: "ACCORD", BodyClass: "Sedan/Saloon", FuelTypePrimary: "Gasoline" }] },
    { results: [{ model: "ACCORD" }] },
    { results: [{ NHTSACampaignNumber: "20V-001", Component: "AIR BAGS", Summary: "Inflator may rupture", Remedy: "Replace it" }] },
  ];
  const fetcher = async () => ({ ok: true, json: async () => responses.shift() });
  const result = await inspectVin("1HGCM82633A004352", fetcher);
  assert.equal(result.vehicle.make, "HONDA");
  assert.equal(result.recall_count, 1);
  assert.equal(result.severe_count, 1);
  assert.equal(result.recalls[0].campaign, "20V-001");
});

test("RX 350 alias mismatch cannot hide the fuel-pump campaign", async () => {
  const calls = [];
  const fetcher = async (url) => {
    calls.push(url);
    let data;
    if (url.includes("DecodeVin")) data = { Results: [{ Make: "LEXUS", Model: "RX 350", ModelYear: "2020" }] };
    else if (url.includes("products/vehicle")) data = { results: [{ model: "RX 350" }] };
    else if (new URL(url).searchParams.get("model") === "RX350") data = { count: 1, results: [{ NHTSACampaignNumber: "20V682000", Summary: "Fuel pump may cause engine stall" }] };
    else data = { count: 0, results: [] };
    return { ok: true, json: async () => data };
  };
  const r = await inspectVin("1HGCM82633A004352", fetcher);
  assert.equal(r.recall_count, 1);
  assert.equal(r.recalls[0].campaign, "20V682000");
  assert.match(r.scope, /does not establish VIN applicability/);
});

test("unmatched models and incomplete responses never become zero recalls", async () => {
  for (const menu of [{ results: [] }, { results: [{ model: "ACCORD" }] }]) {
    const responses = [{ Results: [{ Make: "HONDA", Model: "ACCORD", ModelYear: "2003" }] }, menu,
      { count: 2, results: [{ NHTSACampaignNumber: "20V-001" }] }];
    await assert.rejects(() => inspectVin("1HGCM82633A004352", async () => ({ ok: true, json: async () => responses.shift() })), /not a zero|incomplete/);
  }
});

test("invalid VINs fail before any network request", async () => {
  let calls = 0;
  await assert.rejects(() => inspectVin("not-a-vin", async () => { calls += 1; }), /17-character VIN/);
  assert.equal(calls, 0);
});
