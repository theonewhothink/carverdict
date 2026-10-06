/**
 * Public-data VIN inspection used by /vin-check/.
 *
 * The VIN is sent only to NHTSA's public vPIC and recalls APIs. MotorJury does not
 * persist it. Keeping this in the Worker avoids browser CORS differences and gives the
 * page one stable, same-origin API.
 */

const VIN_RE = /^[A-HJ-NPR-Z0-9]{17}$/;
const SEVERE = /air ?bag|brake|steering|fuel leak|fire|stall|seat ?belt|rollaway|crash|injur|death|explod/i;

export function normalizeVin(value) {
  return String(value || "").toUpperCase().replace(/[\s-]+/g, "");
}

export function validVin(value) {
  return VIN_RE.test(normalizeVin(value));
}

export function severeRecall(row) {
  return SEVERE.test(`${row.Component || ""} ${row.Summary || ""} ${row.Consequence || ""}`);
}

async function getJson(url, fetcher) {
  const response = await fetcher(url, {
    headers: { Accept: "application/json", "User-Agent": "MotorJury/1.0 (motorjury.com)" },
    // VIN requests are private inputs, not reusable public cache keys.
    ...(url.includes("DecodeVin") ? { cache: "no-store" } : { cf: { cacheEverything: true, cacheTtl: 86400 } }),
  });
  if (!response.ok) {
    const error = new Error("The NHTSA service is temporarily unavailable. Please try again.");
    error.status = 502;
    throw error;
  }
  return response.json();
}

function first(...values) {
  return values.find((value) => value != null && String(value).trim() && String(value) !== "0") || "";
}

export async function inspectVin(value, fetcher = fetch) {
  const vin = normalizeVin(value);
  if (!validVin(vin)) {
    const error = new Error("Enter a 17-character VIN using letters and numbers (not I, O or Q).");
    error.status = 400;
    throw error;
  }

  const decoded = await getJson(
    `https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/${encodeURIComponent(vin)}?format=json`,
    fetcher,
  );
  const d = (decoded.Results || [])[0] || {};
  const make = first(d.Make);
  const model = first(d.Model);
  const year = first(d.ModelYear);
  if (!make || !model || !year) {
    const error = new Error("NHTSA could not identify this VIN. Check every character and try again.");
    error.status = 422;
    throw error;
  }

  const menu = await getJson(`https://api.nhtsa.gov/products/vehicle/models?${new URLSearchParams({ make, modelYear: year, issueType: "r" })}`, fetcher);
  const key = (v) => String(v || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (!Array.isArray(menu.results)) throw new Error("The recall model list could not be verified. Check directly with NHTSA.");
  let aliases = [...new Set(menu.results.filter((r) => key(r.model) === key(model)).map((r) => r.model))];
  if (!aliases.length) throw new Error("The decoded model could not be matched to the recall service. This is not a zero-recall result; check directly with NHTSA.");
  // Verified service mismatch: the menu lists RX 350 but recalls use RX350.
  if (key(make) === "LEXUS" && key(model) === "RX350") aliases = ["RX350"];
  const unique = new Map();
  const sourceUrls = [];
  for (const alias of [...new Set(aliases)]) {
    const url = `https://api.nhtsa.gov/recalls/recallsByVehicle?${new URLSearchParams({ make, model: alias, modelYear: year })}`;
    sourceUrls.push(url);
    const data = await getJson(url, fetcher);
    if (!Array.isArray(data.results) || Number(data.count ?? data.Count ?? data.results.length) !== data.results.length) {
      throw new Error("The recall response was incomplete. Verify directly with NHTSA before buying.");
    }
    for (const row of data.results) {
      if (!row.NHTSACampaignNumber) throw new Error("A recall record could not be verified. Check directly with NHTSA.");
      unique.set(row.NHTSACampaignNumber, row);
    }
  }
  const rawRecalls = [...unique.values()];
  const recalls = rawRecalls.map((row) => ({
    campaign: first(row.NHTSACampaignNumber),
    component: first(row.Component),
    summary: first(row.Summary),
    consequence: first(row.Consequence),
    remedy: first(row.Remedy),
    manufacturer: first(row.Manufacturer),
    report_date: first(row.ReportReceivedDate),
    severe: severeRecall(row),
  }));

  return {
    vin,
    vehicle: {
      year, make, model,
      trim: first(d.Trim, d.Series),
      body: first(d.BodyClass, d.VehicleType),
      engine: first(d.EngineModel, d.DisplacementL && `${d.DisplacementL} L`, d.EngineCylinders && `${d.EngineCylinders} cylinders`),
      fuel: first(d.FuelTypePrimary, d.ElectrificationLevel),
      drive: first(d.DriveType),
      plant_country: first(d.PlantCountry),
    },
    recall_count: rawRecalls.length,
    severe_count: rawRecalls.filter((row) => severeRecall(row)).length,
    recalls,
    checked_at: new Date().toISOString(),
    source: "U.S. National Highway Traffic Safety Administration (NHTSA)",
    source_urls: sourceUrls,
    scope: "Model-level campaigns. This does not establish VIN applicability or whether a remedy is complete.",
  };
}
