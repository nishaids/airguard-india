// Bounded, public-only benchmark. No authentication or environment secrets.
const fs = require('node:fs');
const path = require('node:path');
const autocannon = require(process.argv[2]);
const origin='https://webapp-phi-taupe.vercel.app';
const startLatitude=Number(process.argv[3]||'28.3601');
const statuses=[];
const requests=Array.from({length:20},(_,i)=>({
  path:'/api/air-quality/summary?'+new URLSearchParams({lat:(startLatitude+i*.0001).toFixed(4),lon:'75.6',name:'Pilani benchmark'}),
  onResponse(status,body) {
    const data=JSON.parse(body);
    statuses.push({status,state:data.state,no_values:!data.current&&!data.tomorrow});
  }
}));
async function main() {
  const cold=await autocannon({url:origin,connections:1,pipelining:1,amount:20,requests,timeout:15});
  fs.writeFileSync('results/release/autocannon-uncached.json',JSON.stringify({result:cold,responses:statuses},null,2));
  const url=origin+'/api/air-quality/summary?lat=13.1147&lon=80.10981&name=Avadi';
  let response;
  for(let i=0;i<24;i++) {
    response=await fetch(url);
    await response.text();
    if(response.status===200) break;
    if(response.status!==202) throw Error('Warm-up failed: '+response.status);
    await new Promise(resolve=>setTimeout(resolve,5000));
  }
  if(response.status!==200) throw Error('Warm-up did not complete');
  const cached=await autocannon({url,connections:1,pipelining:1,amount:20,timeout:15});
  fs.writeFileSync('results/release/autocannon-cached.json',JSON.stringify(cached,null,2));
  const genuine=JSON.parse(fs.readFileSync('results/release/async_production.json','utf8'));
  const noErrors=[cold,cached].every(r=>r.errors===0&&r.non2xx===0);
  const allQueued=statuses.length===20&&statuses.every(r=>r.status===202&&r.no_values&&r.state==='QUEUED');
  const providerTTFB=genuine.checks.map(c=>c.requests[0].ttfb_ms);
  const report={generated_at:new Date().toISOString(),origin,tool:'autocannon 8.0.0',connections:1,
    cached:{requests:20,p97_5_response_ms:cached.latency.p97_5,errors:cached.errors,non_2xx:cached.non2xx},
    uncached_summary:{requests:20,p97_5_response_ms:cold.latency.p97_5,all_queued_without_values:allQueued,errors:cold.errors,non_2xx:cold.non2xx},
    genuine_provider_misses:{n:providerTTFB.length,first_response_ttfb_ms:providerTTFB,background_completed:genuine.passed},
    notice:'Total response p97.5 conservatively bounds sample p95 TTFB. Summary misses use already cached provider grids; the separate three-grid probe verifies genuine provider misses. These bounded samples are not a concurrency/load guarantee.',
    cached_accepted:cached.latency.p97_5<=800&&cached.errors===0&&cached.non2xx===0,
    accepted:cached.latency.p97_5<=800&&cold.latency.p97_5<=4000&&allQueued&&noErrors&&Math.max(...providerTTFB)<=4000};
  fs.writeFileSync('results/perf.json',JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
  if(!report.accepted) process.exitCode=1;
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
