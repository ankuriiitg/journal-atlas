import importlib.util,pathlib,unittest,xml.etree.ElementTree as E
spec=importlib.util.spec_from_file_location('audit',pathlib.Path(__file__).parents[1]/'scripts/audit_elsevier.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def article(received='2026-01-01',accepted='2026-02-01',online='2026-02-04',typ='Journal Article',issn='1234-5678'):
 def d(s):return ''.join('<'+k+'>'+v+'</'+k+'>' for k,v in zip(['Year','Month','Day'],s.split('-')))
 return E.fromstring(f'<PubmedArticle><MedlineCitation><PMID>1</PMID><Article><Journal><ISSN>{issn}</ISSN></Journal><ArticleTitle>Test</ArticleTitle><PublicationTypeList><PublicationType>{typ}</PublicationType></PublicationTypeList>'+ (f'<ArticleDate DateType="Electronic">{d(online)}</ArticleDate>' if online else '') +f'</Article></MedlineCitation><PubmedData><History><PubMedPubDate PubStatus="received">{d(received)}</PubMedPubDate><PubMedPubDate PubStatus="accepted">{d(accepted)}</PubMedPubDate><PubMedPubDate PubStatus="pubmed">{d("2026-03-01")}</PubMedPubDate></History></PubmedData></PubmedArticle>')
class TestAudit(unittest.TestCase):
 def parse(self,**kw):return m.parse(article(**kw),{'issns':['1234-5678']},{'firstPublicationDate':'2026-02-04'})
 def test_calendar_days(self):
  r=self.parse();self.assertTrue(r['included']);self.assertEqual(r['receivedToAcceptedDays'],31);self.assertEqual(r['acceptedToOnlineDays'],3)
 def test_indexing_not_publication(self):self.assertNotIn('acceptedToOnlineDays',self.parse(online=None))
 def test_mismatch(self):self.assertFalse(self.parse(issn='0000-0000')['included'])
 def test_negative(self):self.assertFalse(self.parse(received='2026-03-01')['included'])
 def test_review(self):self.assertFalse(self.parse(typ='Review')['included'])
 def test_partial_date(self):self.assertIsNone(m.date(E.fromstring('<date><Year>2026</Year><Month>2</Month></date>')))
 def test_future(self):self.assertIsNone(m.date(E.fromstring('<date><Year>2027</Year><Month>2</Month><Day>2</Day></date>')))
 def test_stats(self):self.assertEqual(m.stats([10,20,90]),{'n':3,'mean':40,'median':20,'min':10,'max':90})
 def test_duplicate_doi(self):
  rows=[{'doi':'10.1/ABC','pmid':'1','included':True},{'doi':'10.1/abc','pmid':'2','included':True}]
  self.assertEqual(sum(x['included'] for x in m.deduplicate(rows)),1)
 def test_url(self):self.assertFalse(m.allowed('https://elsevier.com.evil.test'));self.assertFalse(m.allowed('file:///etc/passwd'))
if __name__=='__main__':unittest.main()
