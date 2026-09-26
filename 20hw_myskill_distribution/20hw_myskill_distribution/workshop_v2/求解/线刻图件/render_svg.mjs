// Vector PDF and high-resolution PNG from the same editable SVG.
// Uses an installed Chromium browser; never fetches external page content.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
let pw;
try { pw=require('playwright'); } catch {
  const folder=process.env.PAPER_NODE_MODULES || path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
  pw=require(path.join(folder,'playwright'));
}
const file=path.resolve(process.argv[2]);
const svg=fs.readFileSync(file,'utf8').replace(/<\?xml[^>]*\?>/,'');
const vb=svg.match(/viewBox="([\d.\s]+)"/)[1].trim().split(/\s+/).map(Number);
const width=162,height=width*vb[3]/vb[2];
const candidates=[process.env.PAPER_BROWSER,'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].filter(Boolean);
const exe=candidates.find(x=>fs.existsSync(x));
const browser=await pw.chromium.launch({headless:true,...(exe?{executablePath:exe}:{})});
try {
 const context=await browser.newContext({viewport:{width:1300,height:Math.ceil(1300*vb[3]/vb[2])+30},deviceScaleFactor:4});
 const page=await context.newPage();
 await page.setContent(`<html><head><style>@page{size:${width}mm ${height}mm;margin:0}html,body{margin:0;padding:0;width:${width}mm;height:${height}mm;background:white}svg{display:block;width:100%;height:100%}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}</style></head><body>${svg}</body></html>`);
 await page.evaluate(()=>document.fonts.ready);
 await page.pdf({path:file.replace(/\.svg$/i,'.pdf'),width:width+'mm',height:height+'mm',printBackground:true,margin:{top:0,bottom:0,left:0,right:0},displayHeaderFooter:false});
 await page.locator('svg').screenshot({path:file.replace(/\.svg$/i,'.png')});
} finally {await browser.close();}
