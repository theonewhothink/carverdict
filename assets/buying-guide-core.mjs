/** Local interpretation of a narrow, reviewed brief. This is not a language model. */
export const SOURCES = {
  engine:'https://static.nhtsa.gov/odi/rcl/2020/RCMN-20V064-6563.pdf',
  hybrid:'https://static.nhtsa.gov/odi/tsbs/2021/MC-10190478-9999.pdf',
  vin:'https://www.nhtsa.gov/recalls',
  fuel:'https://www.fueleconomy.gov/feg/findacar.shtml',
};
export function privateQuestion(text) {
  return /[A-HJ-NPR-Z0-9]{17}\b/i.test(text) || /[\w.+-]+@[\w.-]+\.[a-z]{2,}/i.test(text)
    || /(?:\$|€|£|\bUSD\b)\s*\d|\b\d[\d,]*\s*(?:dollars|euros|pounds)\b/i.test(text)
    || /\b(?:\+?\d[\d ()-]{8,}\d)\b/.test(text);
}
export function interpret(text, context={}) {
  const years=[...new Set(text.match(/\b20\d{2}\b/g)||[])];
  const excluded=/\b(prime|plug.in|phev|honda|cr.?v|ford|escape|mazda|cx.?5|subaru|forester|nissan|rogue|lexus|rx.?350|camry|corolla|tesla|bmw|volkswagen|audi|chevrolet|kia|hyundai)\b/i.test(text)
    || years.some(y=>!['2019','2020'].includes(y)) || /\b(?:UK|Europe|Canada|Australia|Portugal)\b/i.test(text);
  const negated=/\b(?:not|isn't|is not)\s+(?:a\s+)?hybrid\b/i.test(text);
  const hybrid=/\bhybrid\b/i.test(text), gas=/\b(gasoline|petrol|gas)\b/i.test(text);
  const powertrain=negated || (hybrid&&gas) ? 'unknown' : hybrid?'hybrid':gas?'gasoline':context.powertrain||'unknown';
  const unrecognized=!/\b(rav.?4|hybrid|gasoline|petrol|viewing|seller|deposit|inspect|inspection|check|ask|recall|campaign|safety|safe|vin|coolant|engine|refuel|refuelling|gauge|cost|budget|mpg|premium|cheaper)\b/i.test(text);
  return { unrecognized, unsupported:excluded, ambiguous:years.length>1, year:years.length===1?years[0]:context.year||'',powertrain,
    intent:/\b(cost|budget|mpg|fuel cost|save money|premium|cheaper)\b/i.test(text)?'budget'
      :/\b(recall|campaign|safe|safety|cleared|vin)\b/i.test(text)?'recall'
      :/\b(refuel|refuelling|gas tank|fuel tank|gauge)\b/i.test(text)?'hybrid':'viewing' };
}
export function guidance(text, context={}) {
  const next=interpret(text,context);
  if(privateQuestion(text)) return {next,blocked:true,title:'Keep private details out of questions',text:'Use the calculator for amounts and the official service for a VIN. Keep emails, phone numbers and personal documents out of this question box.',links:[],actions:[]};
  if(next.unsupported)return {next,title:'This brief does not cover that candidate',text:'Our reviewed example covers 2019–2020 US RAV4 gasoline and Hybrid vehicles. Other cars, markets and the RAV4 Prime need their own evidence. We cannot carry these checks across to them.',links:[['Official VIN check',SOURCES.vin]],actions:[]};
  if(next.unrecognized)return {next,title:'Choose what you need to decide',text:'The guided brief helps with a viewing checklist, recall evidence or a gasoline-versus-Hybrid budget. Choose one of those questions above. We do not have reviewed material for other topics.',links:[],actions:[]};
  if(next.ambiguous||!next.year)return {next,title:'First, confirm the model year',text:'Is the candidate a 2019 or a 2020 US RAV4? The exact version matters. Choose the year, then tell us whether it is gasoline or Hybrid.',links:[],actions:['year']};
  if(next.intent==='budget')return {next,title:'Compare actual candidates with the same assumptions',text:'Start with annual miles, fuel price and each exact version’s MPG. Add actual purchase and insurance quotes, maintenance and repair reserves, and a resale assumption. An unknown cost stays unknown. Fuel savings alone cannot decide which car to buy.',links:[['Match the exact EPA version',SOURCES.fuel]],actions:['budget']};
  if(next.intent==='recall')return {next,title:'A model-level campaign list cannot clear a VIN',text:'Campaign 20V-064 concerns an engine-block defect in certain 2019–2020 RAV4 gasoline and Hybrid vehicles. Ask a dealer to establish applicability and remedy completion for the actual VIN. A listed campaign is neither proof of an affected car nor proof of completed work.',links:[['Manufacturer remedy notice',SOURCES.engine],['Official VIN check',SOURCES.vin]],actions:['checklist']};
  if(next.intent==='hybrid'&&next.powertrain==='gasoline')return {next,title:'The refuelling program is Hybrid-specific',text:'Toyota’s 20TE04 support program is not a blanket gasoline-RAV4 issue. For this gasoline candidate, verify the engine-block campaign by VIN and obtain its service and repair history.',links:[['Engine-block remedy notice',SOURCES.engine]],actions:['checklist']};
  const extra=next.powertrain==='gasoline'?'':next.powertrain==='hybrid'?' For this Hybrid, ask about refuelling symptoms and program 20TE04 invoices; the dealer must confirm current eligibility.':' Confirm gasoline or Hybrid before applying the refuelling-program check.';
  return {next,title:'Go to the viewing with three requests',text:'Ask for dealer evidence of applicable recall remedies, invoices explaining coolant loss or engine work, and permission for an independent inspection. Those requests tell you more about the actual car than a complaint total.'+extra,links:[['Engine-block remedy notice',SOURCES.engine],...(next.powertrain==='hybrid'?[['Hybrid support program',SOURCES.hybrid]]:[])],actions:['checklist','budget']};
}
export function questionPayload(text, context, history=[]) {
  if(privateQuestion(text))throw new Error('Private details must not be sent');
  return {mode:'buying',buying_context:{year:['2019','2020'].includes(context.year)?context.year:'',powertrain:['gasoline','hybrid'].includes(context.powertrain)?context.powertrain:'unknown'},messages:[...history.slice(-4),{role:'user',content:String(text).slice(0,600)}]};
}
export function safeLink(value, origin) {
  try {const url=new URL(value,origin);return url.origin===origin&&url.pathname.startsWith('/')||url.protocol==='https:'&&['www.nhtsa.gov','api.nhtsa.gov','static.nhtsa.gov','www.toyota.com','pressroom.toyota.com','www.fueleconomy.gov'].includes(url.hostname)?url.href:null;}catch{return null;}
}
