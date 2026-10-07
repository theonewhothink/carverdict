/** Cash-purchase scenarios in USD; unknown inputs remain unknown. No valuations. */
export function number(value, min = 0, max = 2000000) {
  if (value == null || String(value).trim() === "") return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= min && n <= max ? n : null;
}

export function fuelCost(miles, mpg, price) {
  miles = number(miles, 0, 200000); mpg = number(mpg, 1, 200); price = number(price, 0.01, 30);
  return [miles, mpg, price].includes(null) ? null : miles / mpg * price;
}

export function ownership(car, common) {
  const annualFuel = fuelCost(common.miles, car.mpg, common.fuel);
  const values = {
    price: number(car.price), insurance: number(car.insurance),
    maintenance: number(car.maintenance), reserve: number(car.reserve),
    resale: number(car.resale), years: number(common.years, 1, 20), annualFuel,
  };
  const missing = Object.keys(values).filter((k) => values[k] === null);
  if (missing.length) return { annualFuel, total: null, missing };
  const running = annualFuel + values.insurance + values.maintenance + values.reserve;
  return { annualFuel, running, total: values.price - values.resale + running * values.years, missing: [] };
}

export function compare(a, b, common) {
  const left = ownership(a, common), right = ownership(b, common);
  return { left, right, difference: left.total === null || right.total === null ? null : right.total - left.total };
}
