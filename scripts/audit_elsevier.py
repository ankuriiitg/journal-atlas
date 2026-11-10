"""Reproducible, resumable Elsevier catalog audit; public metadata only."""
import argparse,concurrent.futures as cf,datetime as dt,hashlib,json,pathlib,re,statistics,subprocess,threading,time,urllib.request,urllib.parse,urllib.error,xml.etree.ElementTree as ET
from html.parser import HTMLParser
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'data/elsevier-audit';OUT.mkdir(parents=True,exist_ok=True)
CUTOFF='2026-11-10';TARGET=100
CAT=[j for j in json.loads((ROOT/'data/catalog.json').read_text()) if j['publisher']=='Elsevier']
class Gate:
 def __init__(self,delay):self.delay=delay;self.next=0.;self.lock=threading.Lock()
 def wait(self):
  with self.lock:
   delay=max(0,self.next-time.monotonic());self.next=time.monotonic()+delay+self.delay
  if delay:time.sleep(delay)
 def backoff(self,seconds):
  with self.lock:self.next=max(self.next,time.monotonic()+seconds)
GATES={'epmc':Gate(.5),'ncbi':Gate(1.4),'publisher':Gate(1.2)}
BLOCKED=set();BLOCK_LOCK=threading.Lock()
ALLOWED=('sciencedirect.com','elsevier.com','cell.com','elsevierhealth.com','elsevier.es')
def allowed(url):
 u=urllib.parse.urlparse(url);return u.scheme in ('https','http') and any(u.hostname==d or (u.hostname or '').endswith('.'+d) for d in ALLOWED)
class SafeRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if not allowed(newurl):raise ValueError('Publisher redirect outside supported domains')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
PUBLISHER_OPENER=urllib.request.build_opener(SafeRedirect())
def fetch(url,kind):
 for attempt in range(3):
  GATES[kind].wait()
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'JournalAtlas/1.0 (public scholarly metadata audit)','Accept':'application/json,application/xml,text/html'})
   opener=PUBLISHER_OPENER.open if kind=='publisher' else urllib.request.urlopen
   with opener(req,timeout=35) as r:return r.read(12_000_000),r.geturl()
  except urllib.error.HTTPError as e:
   if kind=='publisher' or e.code not in (429,500,502,503,504) or attempt==2:raise
   wait=min(90,max(20*(attempt+1),int(e.headers.get('Retry-After','30')) if e.headers.get('Retry-After','').isdigit() else 30));GATES[kind].backoff(wait)
  except (TimeoutError,OSError):
   if kind=='publisher' or attempt==2:raise
   time.sleep(3*(attempt+1))
class VisibleText(HTMLParser):
 def __init__(self):super().__init__();self.hidden=0;self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','noscript'):self.hidden+=1
 def handle_endtag(self,tag):
  if tag in ('script','style','noscript'):self.hidden=max(0,self.hidden-1)
 def handle_data(self,s):
  if not self.hidden:self.parts.append(s)
METRICS={'firstDecision':'Submission to first decision','decisionAfterReview':'Submission to decision after review','submissionToAcceptance':'Submission to acceptance','acceptanceToPublication':'Acceptance to online publication'}
def publisher_check(j):
 url=j.get('homepage') or ''
 if not url:return {'status':'no_homepage','metrics':{}}
 if not allowed(url):return {'status':'outside_supported_publisher_domains','url':url,'metrics':{}}
 host=urllib.parse.urlparse(url).hostname
 with BLOCK_LOCK:
  if host in BLOCKED:return {'status':'domain_access_limited_not_individually_retrieved','url':url,'metrics':{}}
 try:
  b,final=fetch(url,'publisher');p=VisibleText();p.feed(b.decode('utf8','replace'));text=' '.join(' '.join(p.parts).split())
  if re.search(r'(verify you are human|access denied|site unavailable|unable to access this site|just a moment)',text,re.I):
   with BLOCK_LOCK:BLOCKED.add(host)
   return {'status':'publisher_access_blocked','url':url,'metrics':{}}
  values={}
  for key,label in METRICS.items():
   m=re.search(r'(\d+(?:\.\d+)?)\s+days\s+'+re.escape(label)+r'\b',text,re.I)
   if m:values[key]={'value':float(m[1]),'unit':'days','label':label,'sourceUrl':final,'year':None,'sampleSize':None,'evidenceType':'publisher-reported','notes':'Publisher homepage retrieved '+CUTOFF+'. Reporting year, mean/median and denominator not disclosed in extracted text. First decision may include desk rejections.'}
  return {'status':'timelines_found' if values else 'no_timeline_labels_extracted','url':final,'metrics':values,'responseSha256':hashlib.sha256(b).hexdigest()}
 except Exception as e:
  if isinstance(e,urllib.error.HTTPError) and e.code in (403,429):
   with BLOCK_LOCK:BLOCKED.add(host)
  return {'status':'publisher_retrieval_error','url':url,'error':str(e),'metrics':{}}
def date(e):
 if e is None:return None
 try:
  y=e.findtext('Year') or e.findtext('year');m=e.findtext('Month') or e.findtext('month');d=e.findtext('Day') or e.findtext('day')
  if not str(m).isdigit():m=dt.datetime.strptime(m[:3],'%b').month
  s=dt.date(int(y),int(m),int(d)).isoformat();return s if s<=CUTOFF else None
 except (ValueError,TypeError):return None
def stats(v):
 return {'n':len(v),'mean':round(statistics.mean(v),1),'median':statistics.median(v),'min':min(v),'max':max(v)} if v else None
def parse(a,j,record):
 pmid=a.findtext('MedlineCitation/PMID');doi=a.findtext("PubmedData/ArticleIdList/ArticleId[@IdType='doi']");title=a.find('MedlineCitation/Article/ArticleTitle')
 title=''.join(title.itertext()) if title is not None else record.get('title','')
 hist={e.get('PubStatus'):date(e) for e in a.findall('PubmedData/History/PubMedPubDate')}
 received,accepted=hist.get('received'),hist.get('accepted')
 online=[date(e) for e in a.findall("MedlineCitation/Article/ArticleDate[@DateType='Electronic']")]+[hist.get('epublish'),hist.get('aheadofprint')]
 online=min((x for x in online if x),default=None);pub=online or record.get('firstPublicationDate')
 types=[e.text for e in a.findall('MedlineCitation/Article/PublicationTypeList/PublicationType')]
 issns=[e.text for e in a.findall('MedlineCitation/Article/Journal/ISSN')]+[a.findtext('MedlineCitation/MedlineJournalInfo/ISSNLinking')]
 r={'pmid':pmid,'doi':doi,'title':title,'received':received,'accepted':accepted,'online':online,'publicationDate':pub,'publicationYear':int(pub[:4]) if pub and re.match(r'^\d{4}',pub) else None,'types':types,'sourceUrl':f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/','paperUrl':f'https://doi.org/{doi}' if doi else f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/','history':hist,'included':False}
 banned={'Editorial','Letter','Comment','Published Erratum','Retraction of Publication','Retracted Publication','News','Review','Systematic Review','Meta-Analysis'}
 reason=None
 if not set(issns)&set(j['issns']):reason='ISSN mismatch'
 elif set(types)&banned or re.search(r'^(retraction|corrigendum|erratum|correction)',title,re.I):reason='Non-primary-research or retracted record'
 elif 'Journal Article' not in types:reason='Research article classification unconfirmed'
 elif not received or not accepted:reason='Missing complete received/accepted dates'
 elif received>accepted:reason='Acceptance precedes receipt'
 elif not pub or pub>CUTOFF:reason='Publication date unavailable or after cutoff'
 if reason:r['exclusionReason']=reason;return r
 r['included']=True;r['receivedToAcceptedDays']=(dt.date.fromisoformat(accepted)-dt.date.fromisoformat(received)).days
 if online and online>=accepted:
  r['acceptedToOnlineDays']=(dt.date.fromisoformat(online)-dt.date.fromisoformat(accepted)).days;r['receivedToOnlineDays']=(dt.date.fromisoformat(online)-dt.date.fromisoformat(received)).days
 elif online:r['onlineDateWarning']='Online date precedes acceptance; excluded from production calculation'
 return r
def deduplicate(records):
 seen=set()
 for r in records:
  key=(r.get('doi') or r.get('pmid') or '').strip().lower()
  if key in seen:r.update(included=False,exclusionReason='Duplicate DOI/PMID')
  elif key:seen.add(key)
 return records
def audit(j):
 path=OUT/(j['id']+'.json')
 if path.exists():
  cached=json.loads(path.read_text())
  if cached['status']!='retrieval_error':return cached
 r={'journalId':j['id'],'title':j['title'],'issns':j['issns'],'homepage':j.get('homepage'),'checkedAt':CUTOFF,'methodVersion':'pubmed-history-v2','target':TARGET,'status':'pending','queries':[],'articles':[],'publisherPage':publisher_check(j)}
 try:
  issns=[s for s in j['issns'] if re.fullmatch(r'\d{4}-\d{3}[\dX]',s,re.I)]
  if not issns:r['status']='missing_issn'
  else:
   end=CUTOFF;seen=set()
   for attempt in range(3):
    query='('+' OR '.join('ISSN:'+s for s in issns)+f') AND SRC:MED AND FIRST_PDATE:[1800-01-01 TO {end}] sort_date:y'
    url='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urllib.parse.urlencode({'query':query,'format':'json','pageSize':TARGET,'resultType':'lite'})
    b,_=fetch(url,'epmc');d=json.loads(b)
    if 'resultList' not in d:raise ValueError('Unexpected discovery response')
    raw=d['resultList'].get('result',[]);r['queries'].append({'url':url,'hitCount':d.get('hitCount'),'returned':len(raw),'end':end})
    items=[x for x in raw if x.get('id') not in seen];seen.update(x.get('id') for x in items)
    if not items:break
    ids={x['id']:x for x in items}
    u='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?'+urllib.parse.urlencode({'db':'pubmed','id':','.join(ids),'retmode':'xml','tool':'JournalAtlas'})
    b,_=fetch(u,'ncbi');root=ET.fromstring(b)
    if root.find('ERROR') is not None:raise ValueError(root.findtext('ERROR'))
    parsed=[parse(a,j,ids.get(a.findtext('MedlineCitation/PMID'),{})) for a in root.findall('PubmedArticle')]
    if not parsed:raise ValueError('No article records in history response')
    r['queries'][-1].update(historyUrl=u,responseSha256=hashlib.sha256(b).hexdigest());r['articles'].extend(parsed)
    if any(a['included'] for a in r['articles']):break
    years=[int(x['firstPublicationDate'][:4]) for x in items if x.get('firstPublicationDate')]
    if not years:break
    end=f'{min(years)-1}-12-31'
   deduplicate(r['articles'])
   valid=[a for a in r['articles'] if a['included']]
   if valid:
    year=max(a['publicationYear'] for a in valid);cohort=[a for a in valid if a['publicationYear']==year]
    for a in r['articles']:
     if a['included'] and a['publicationYear']!=year:a.update(included=False,exclusionReason='Older publication cohort kept separate')
    r.update(status='history_sample_available',year=year,sampleSize=len(cohort),receivedToAccepted=stats([a['receivedToAcceptedDays'] for a in cohort]),acceptedToOnline=stats([a['acceptedToOnlineDays'] for a in cohort if 'acceptedToOnlineDays' in a]),receivedToOnline=stats([a['receivedToOnlineDays'] for a in cohort if 'receivedToOnlineDays' in a]))
   else:r['status']='no_matching_pubmed_records' if not r['articles'] else 'no_usable_history_in_screened_records'
 except Exception as e:r.update(status='retrieval_error',error=f'{type(e).__name__}: {e}')
 r['screened']=len(r['articles']);r['excluded']=sum(not a['included'] for a in r['articles'])
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(r,ensure_ascii=False,separators=(',',':')));tmp.replace(path);return r
def package():
 from collections import Counter
 counts=Counter();pubcounts=Counter();profiles={};screened=included=0
 for j in CAT:
  p=OUT/(j['id']+'.json');a=json.loads(p.read_text()) if p.exists() else {'status':'pending','articles':[],'publisherPage':{'status':'not_checked'}}
  counts[a['status']]+=1;pubcounts[a['publisherPage']['status']]+=1;screened+=len(a['articles']);included+=a.get('sampleSize',0)
  profiles[j['id']]={k:a.get(k) for k in ['status','year','sampleSize','screened','receivedToAccepted','acceptedToOnline','receivedToOnline']};profiles[j['id']].update(publisherPageStatus=a['publisherPage']['status'],publisherMetrics=a['publisherPage'].get('metrics',{}))
 meta={'total':len(CAT),'completed':len(CAT)-counts['pending'],'states':dict(counts),'publisherStates':dict(pubcounts),'papersScreened':screened,'papersIncluded':included,'cutoff':CUTOFF,'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'profiles':profiles}
 (ROOT/'data/elsevier-audit-index.json').write_text(json.dumps(meta,separators=(',',':')))
 print(json.dumps({k:v for k,v in meta.items() if k!='profiles'}),flush=True)
 return meta
def checkpoint(push):
 package()
 if push:
  subprocess.run(['git','add','data/elsevier-audit','data/elsevier-audit-index.json'],cwd=ROOT,check=True)
  if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:
   subprocess.run(['git','commit','-m','Save Elsevier public-metadata audit checkpoint'],cwd=ROOT,check=True)
   subprocess.run(['git','push','origin','HEAD:main'],cwd=ROOT,check=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);ap.add_argument('--push',action='store_true');ap.add_argument('--package-only',action='store_true');args=ap.parse_args()
 if args.package_only:package()
 else:
  selected=CAT[:args.limit] if args.limit else CAT
  # Limits apply to starts across all worker threads, not independently per worker.
  try:
   with cf.ThreadPoolExecutor(max_workers=24) as pool:
    futures=[pool.submit(audit,j) for j in selected]
    for n,f in enumerate(cf.as_completed(futures),1):
     f.result()
     if n%100==0:checkpoint(args.push)
  finally:checkpoint(args.push)
