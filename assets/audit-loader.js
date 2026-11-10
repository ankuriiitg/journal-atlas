/* Merge static, source-linked audit snapshots into journal profiles. No live analysis. */
(()=>{const original=window.fetch.bind(window);window.fetch=async(input,options)=>{const url=typeof input==='string'?input:input instanceof Request?input.url:String(input);if(!url.endsWith('/data/catalog.json')&&!url.endsWith('data/catalog.json'))return original(input,options);const response=await original(input,options);try{const result=await original('./data/elsevier-audit-index.json');if(!result.ok)return response;const audit=await result.json();const catalog=await response.clone().json();
const publisherMetrics = {
  "S108944336": [
    null,
    2,
    "https://www.sciencedirect.com/science/journal/13826689"
  ],
  "S4210239029": [
    3.4,
    7,
    "https://www.sciencedirect.com/journal/journal-of-neurorestoratology/about/call-for-papers"
  ],
  "S2898459094": [
    0.2,
    22,
    "https://www.sciencedirect.com/journal/revista-de-senologia-y-patologia-mamaria/about/insights"
  ],
  "S133768115": [
    5.2,
    32,
    "https://www.sciencedirect.com/science/journal/09218890"
  ]
};
const additionalImpactFactors={"Neurocomputing": 6.7, "Engineering Applications of Artificial Intelligence": 9.0, "European Journal of Control": 2.6, "Image and Vision Computing": 5.0, "Journal of Systems Architecture": 5.3, "Computers and Electronics in Agriculture": 10.3, "Journal of Parallel and Distributed Computing": 3.4, "Journal of Symbolic Computation": 0.9, "International Journal of Fatigue": 7.0};
for (const j of catalog) {
const impactValue = additionalImpactFactors[j.title];
if (impactValue !== undefined && j.publisher === "Elsevier") j.metrics.impactFactor ??= {value:impactValue,label:"Journal Impact Factor",sourceUrl:"https://www.sciencedirect.com/browse/calls-for-papers",evidenceType:"publisher-reported",notes:"Publisher calls-for-papers listing checked 2026-11-10. Metric year unspecified in listing."};

  const official = publisherMetrics[j.id];
  if (official && j.publisher === 'Elsevier') {
    const [impactFactor, firstDecision, sourceUrl] = official;
    const provenance = {sourceUrl, evidenceType: 'publisher-reported', notes: 'ScienceDirect publisher snapshot checked 2026-11-10. Reporting period not stated in the retrieved text.'};
    if (impactFactor !== null) j.metrics.impactFactor ??= {...provenance, value: impactFactor, label: 'Journal Impact Factor'};
    j.metrics.firstDecision ??= {...provenance, value: firstDecision, unit: 'days', label: 'Submission to first decision'};
  }
  const a = audit.profiles[j.id];if(!a)continue;const source='./elsevier-audit.html?journal='+encodeURIComponent(j.id);j.notes.push('Paper-history audit: '+a.status.replaceAll('_',' ')+'. PubMed coverage is incomplete; catalog affiliation does not verify the current publisher.');j.sources.push({url:source,title:'Paper dates, sample calculations and audit status'});for(const [k,m]of Object.entries(a.publisherMetrics||{}))if(!j.metrics[k])j.metrics[k]=m;for(const [key,field,label]of [['paperReceivedToAccepted','receivedToAccepted','Received to accepted — paper-history sample'],['paperAcceptedToOnline','acceptedToOnline','Accepted to online — paper-history sample'],['paperReceivedToOnline','receivedToOnline','Received to online — paper-history sample']]){const v=a[field];if(!v||a.status!=='history_sample_available')continue;j.metrics[key]={value:v.mean,unit:'days',year:a.year,label,statistic:'mean',sampleSize:v.n,sourceUrl:source,reportingPeriod:a.year+' publication cohort',notes:'Mean of '+v.n+' accepted, indexed papers. Median '+v.median+' days; range '+v.min+'–'+v.max+'. Includes revisions; not editor or first-review time.'+(v.n<5?' Very small sample; not a journal-wide average.':'')}}}return new Response(JSON.stringify(catalog),{status:200,headers:{'Content-Type':'application/json'}})}catch(error){console.warn('Optional audit snapshot unavailable');return response}}})();
