import {normalize} from './catalogue-core.mjs';
export const MAX_SAVED=100;
export function cleanSaved(value){return Array.isArray(value)?[...new Set(value.filter(x=>typeof x==='string'&&/^\/library\/[a-z0-9/-]+\/(?:#m-[a-z0-9-]+)?$/.test(x)))].slice(0,MAX_SAVED):[];}
export function changeSaved(saved,url){const values=cleanSaved(saved);if(!cleanSaved([url]).length)return values;return values.includes(url)?values.filter(x=>x!==url):values.length<MAX_SAVED?[...values,url]:values;}
export function discoveryTopic(question){const q=normalize(question);if(/\b(buy|buying|recall|reliable|reliability|cost|vin|rav4)\b/.test(q))return 'buying';if(/\b(door|doors|gullwing|frame|mercedes|300 sl)\b/.test(q))return 'doors';if(/\b(roadster|convertible|lightweight|miata|mx 5|roof|open top)\b/.test(q))return 'roadster';if(/\b(race|racing|m3|bmw|homologation)\b/.test(q))return 'racing';if(/\b(engine|engines|turbo|supercar|f40|miura|nsx|ferrari|lamborghini|honda)\b/.test(q))return 'engine';return 'all';}
export function compareProfiles(rows,profiles){return rows.slice(0,3).map(r=>({row:r,profile:profiles.find(p=>p.url===r.u)||null}));}
