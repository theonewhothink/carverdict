// Test the compilation boundary that Cloudflare uses, rather than only importing
// the source client. Wrangler supplies esbuild in both npm and pnpm installations.
import {createRequire} from 'node:module';
import {realpathSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
let build;
try {({build}=require('esbuild'));} catch {
 const fromWrangler=createRequire(realpathSync(new URL('../node_modules/wrangler/package.json',import.meta.url)));
 ({build}=fromWrangler('esbuild'));
}
export async function compiledDashboard({minify=true}={}) {
 const result=await build({entryPoints:[fileURLToPath(new URL('../workers/dashboard-ui.mjs',import.meta.url))],bundle:true,platform:'browser',format:'esm',target:'es2022',keepNames:true,minify,write:false});
 return import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
}
