// node workers/calc.test.mjs — unit tests for calculator math (Phase 5 acceptance)
import { calcTrueCost, calcRepairOrSell, calcEvVsGas, bandFor } from "./router_worker.js";

let fails = 0;
const eq = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) { fails++; console.error(`FAIL ${name}: got ${JSON.stringify(got)} want ${JSON.stringify(want)}`); }
  else console.log(`ok  ${name}`);
};

// bands
eq("band age0", bandFor(0), [450, 900]);
eq("band age7", bandFor(7), [950, 1700]);
eq("band age20", bandFor(20), [1500, 2800]);

// true cost: 2018 vehicle in 2026 -> age0=8; keep 2 years -> ages 8,9
// age8 band [950,1700], age9 band [1200,2200]; fuel 1850
const tc = calcTrueCost({ year: 2018, annual_fuel_cost: 1850, keep_years: 2 });
eq("truecost total_low", tc.total_low, 1850 + 950 + 1850 + 1200);
eq("truecost total_high", tc.total_high, 1850 + 1700 + 1850 + 2200);
eq("truecost annual_low", tc.annual_low, Math.round((1850 + 950 + 1850 + 1200) / 2));

// repair or sell
eq("ros sell", calcRepairOrSell({ vehicle_value: 4000, repair_cost: 2400 }).verdict, "SELL");
eq("ros repair", calcRepairOrSell({ vehicle_value: 10000, repair_cost: 1500 }).verdict, "REPAIR");
eq("ros borderline", calcRepairOrSell({ vehicle_value: 8000, repair_cost: 2400 }).verdict, "BORDERLINE");

// ev vs gas: 12000mi, gas 3.5/28mpg = 1500; ev 12000/100*30*0.16 = 576
const evg = calcEvVsGas({});
eq("evgas gas", evg.gas_annual_fuel, 1500);
eq("evgas ev", evg.ev_annual_energy, 576);
eq("evgas saves", evg.ev_saves, 924);

process.exit(fails ? 1 : 0);
