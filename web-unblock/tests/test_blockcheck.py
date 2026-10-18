#!/usr/bin/env python3
"""Offline detector tests: python tests/test_blockcheck.py"""
import pathlib,sys,unittest
S=pathlib.Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(S))
from blockcheck import check
from unblock_fetch import parse_page
class Verdicts(unittest.TestCase):
 def assert_kind(self,k,s,b,u='https://example.com/story',h=None):
  self.assertEqual(check(s,b,u,h).kind,k)
 def test_cloudflare_403(self):self.assert_kind('blocked',403,'<title>Just a moment...</title>')
 def test_cloudflare_200(self):self.assert_kind('blocked',200,'<title>Just a moment...</title>')
 def test_cloudflare_header(self):self.assert_kind('blocked',200,'<h1>Checking</h1>',h={'Cf-Mitigated':'challenge'})
 def test_datadome(self):self.assert_kind('captcha',403,'<script src="https://geo.captcha-delivery.com/captcha/"></script>')
 def test_px(self):self.assert_kind('captcha',403,'<div id="px-captcha">Press &amp; Hold</div>')
 def test_aws(self):self.assert_kind('blocked',202,'<script>awsWafCookieDomainList = []</script>')
 def test_amazon(self):self.assert_kind('captcha',200,'<p>Type the characters you see in this image</p><form action="/errors/validateCaptcha"></form>')
 def test_reddit(self):self.assert_kind('blocked',403,'<body>You have been blocked by network security</body>')
 def test_reddit_social(self):self.assert_kind('blocked',200,'<p>Your user agent facebookexternalhit/1.1 has been identified as a social crawler. Please submit a bug report.</p>')
 def test_statuses(self):
  for s in (403,429,503):self.assert_kind('blocked',s,'<h1>Oops</h1>')
  self.assert_kind('gone',404,'<html>Page not found</html>')
 def test_login(self):
  self.assert_kind('login',200,'<body>Log in to continue</body>')
  self.assert_kind('login',200,'<h1>Sign in</h1>',u='https://example.com/accounts/login/')
 def test_js_shell(self):self.assert_kind('js',200,'<html><body><div id="root"></div><script src="/app.js"></script></body></html>')
 def test_empty(self):self.assert_kind('empty',200,'')
 def test_real(self):self.assert_kind('ok',200,'<h1>A useful article</h1>'+('Actual story text about the subject. '*20))
 def test_real_about_captcha(self):self.assert_kind('ok',200,'<h1>Guide to captcha</h1>'+('An article discussing captcha and Cloudflare. '*130))
 def test_tiny_real(self):self.assert_kind('ok',200,'<h1>Example Domain</h1><p>This domain is for use in illustrative examples in documents. You may use this domain in literature without prior coordination or asking for permission.</p>')
 def test_youtube_footer(self):self.assert_kind('js',200,'<body>YouTube About Press Copyright Contact us Creators Advertise Developers Terms Privacy Policy & Safety How YouTube works Test new features</body>')
 def test_parse(self):
  raw='<meta property="og:image" content="/large.jpg"><meta name="twitter:image" content="/card.jpg"><link rel="alternate" type="application/rss+xml" href="/rss"><script type="application/ld+json">{"@type":"Article","headline":"Good"}</script><img src="/small.png">'
  p=parse_page(raw,'https://example.com/story')
  self.assertEqual(p['images'][:2],['https://example.com/large.jpg','https://example.com/card.jpg'])
  self.assertEqual(p['data'][0]['headline'],'Good')
  self.assertEqual(p['sources'][0][1],'https://example.com/rss')
if __name__=='__main__':unittest.main(verbosity=2)
