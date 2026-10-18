#!/usr/bin/env python3
"""Read a public page when a normal fetch is blocked; stop at the first route with real content.

    python unblock_fetch.py URL [--want text|html|images|media] [--out DIR]

Writes result.json (route, URL, files and attempts), page.txt / page.html or images / media.
Run from any directory. Python needs requests; Pillow is optional for image checks.
Browser route needs the repo's Playwright+Chromium, media route needs yt-dlp.
"""
import argparse
import datetime as dt
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import signal
import tempfile
import subprocess
import sys
import time
from urllib.parse import urljoin, urlparse, quote, urlencode
import requests
from blockcheck import check, visible_text

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
HEADERS = {'User-Agent': UA, 'Accept-Language':'en-US,en;q=0.9',
           'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'}
MAX_BYTES = 12 * 1024 * 1024
SOCIAL = ('youtube.com','youtu.be','vimeo.com','tiktok.com','instagram.com','x.com','twitter.com','reddit.com')


def run_bounded(cmd, timeout, env=None):
    """Kill the whole process group on deadline; children cannot hold a captured pipe open."""
    with tempfile.TemporaryFile(mode='w+t',encoding='utf-8',errors='replace') as so, \
         tempfile.TemporaryFile(mode='w+t',encoding='utf-8',errors='replace') as se:
        p=subprocess.Popen(cmd,stdout=so,stderr=se,env=env,start_new_session=True)
        try:p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
            raise subprocess.TimeoutExpired(cmd,timeout)
        so.seek(0);se.seek(0)
        return subprocess.CompletedProcess(cmd,p.returncode,so.read(),se.read())

class Bits(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta=[]; self.links=[]; self.images=[]; self.scripts=[]; self._script=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta': self.meta.append(a)
        if tag=='link': self.links.append(a)
        if tag in ('img','video','audio','source'):
            self.images.append((tag,a))
        if tag=='script': self._script=a; self.scripts.append([a,''])
    def handle_data(self,s):
        if self._script is not None: self.scripts[-1][1]+=s
    def handle_endtag(self,tag):
        if tag=='script': self._script=None


def fetch(url, *, headers=None, proxy=None, timeout=20, max_bytes=MAX_BYTES):
    kw={'headers':headers or HEADERS,'timeout':(8,timeout),'stream':True}
    if proxy: kw['proxies']={'http':proxy,'https':proxy}
    r=requests.get(url,**kw)
    data=bytearray()
    for b in r.iter_content(65536):
        data.extend(b)
        if len(data)>max_bytes: raise ValueError(f'page exceeds {max_bytes//1024//1024} MB cap')
    return r,bytes(data)


def decode(data,resp):
    return data.decode(resp.encoding or 'utf-8',errors='replace')


def plain(html_text):
    # Use the source's main text extractor when it is installed; stdlib fallback otherwise.
    try:
        import trafilatura
        return trafilatura.extract(html_text,include_links=True,include_images=True,favor_recall=True) or visible_text(html_text)
    except ImportError:
        return visible_text(html_text)


def parse_page(body,base):
    b=Bits()
    try: b.feed(body)
    except Exception: pass
    images=[]; media=[]; data=[]; sources=[]
    for m in b.meta:
        key=(m.get('property') or m.get('name') or '').lower()
        value=m.get('content','')
        if key in ('og:image','og:image:url','twitter:image','twitter:image:src') and value:
            images.append(urljoin(base,value))
        if key in ('og:video','og:video:url','og:audio','og:audio:url') and value:
            media.append(urljoin(base,value))
    for tag,a in b.images:
        u=a.get('src') or a.get('data-src') or a.get('poster')
        if u and not u.startswith('data:'):
            (media if tag in ('video','audio','source') else images).append(urljoin(base,u))
        srcset=a.get('srcset','')
        for item in srcset.split(','):
            u=item.strip().split(' ')[0]
            if u and not u.startswith('data:'): images.append(urljoin(base,u))
    for a in b.links:
        rel=' '.join(a.get('rel',[]) if isinstance(a.get('rel'),list) else [a.get('rel','')]).lower()
        typ=a.get('type','').lower(); href=a.get('href')
        if not href: continue
        if any(x in rel for x in ('alternate','sitemap')) or 'oembed' in typ:
            sources.append((typ or rel,urljoin(base,href)))
    for a,raw in b.scripts:
        typ=a.get('type','')
        if typ=='application/ld+json' or a.get('id')=='__NEXT_DATA__':
            try: data.append(json.loads(raw))
            except (ValueError,TypeError): pass
    # r.jina.ai returns Markdown, not HTML: keep linked media references.
    for url in re.findall(r'!?\[[^\]]*\]\((https?://[^) ]+)',body):
        ext=urlparse(url).path.lower()
        if re.search(r'\.(?:png|jpe?g|gif|webp|avif|svg)(?:$|\?)',ext): images.append(url)
        if re.search(r'\.(?:mp4|webm|mov|mp3|m4a|m3u8)(?:$|\?)',ext): media.append(url)
    return {'images':list(dict.fromkeys(images))[:300], 'media':list(dict.fromkeys(media))[:100],
            'data':data[:30], 'sources':list(dict.fromkeys(sources))[:50]}


def is_image(resp,data):
    ct=resp.headers.get('content-type','').lower()
    if not ct.startswith('image/'): return False
    try:
        from PIL import Image
        from io import BytesIO
        im=Image.open(BytesIO(data)); im.verify()
    except ImportError: pass
    except Exception: return False
    return len(data)>200


def safe_file_name(url,index,content_type=''):
    suf=Path(urlparse(url).path).suffix.lower()
    if suf not in ('.png','.jpg','.jpeg','.gif','.webp','.avif','.svg','.mp4','.webm','.mp3','.m4a','.ogg'):
        suf={ 'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','image/gif':'.gif','video/mp4':'.mp4' }.get(content_type.split(';')[0],'.bin')
    return f'{index:02d}{suf}'


class Ladder:
    def __init__(self,url,want,out, *, wait=25, limit=8, no_browser=False, no_cache=False, no_media=False, storage=None, save_state=False):
        if urlparse(url).scheme not in ('http','https'): raise ValueError('URL must start with http:// or https://')
        self.url=url; self.want=want; self.out=Path(out); self.out.mkdir(parents=True,exist_ok=True)
        self.wait=wait; self.limit=limit; self.no_browser=no_browser; self.no_cache=no_cache; self.no_media=no_media
        self.storage=storage; self.save_state=save_state
        self.attempts=[]; self.seen=set(); self.partial=[]; self.result=None
    def note(self,route,reason,ok=False):
        item={'route':route,'ok':ok,'reason':str(reason)[:300]}
        self.attempts.append(item)
        print(f"{'WIN' if ok else 'try'} {route}: {item['reason']}",file=sys.stderr,flush=True)
    def save(self,route,body, *, source=None, pageurl=None, kind='html', parsed=None, extra=None):
        pageurl=pageurl or self.url
        parsed=parsed or parse_page(body,pageurl)
        ext='html' if kind=='html' else 'txt'
        p=self.out/('page.'+ext); p.write_text(body,encoding='utf-8')
        text=plain(body) if kind=='html' else body
        t=self.out/'page.txt'; t.write_text(text,encoding='utf-8')
        files=[str(p)] if p==t else [str(p),str(t)]
        # JSON-LD / __NEXT_DATA__ can be large, keep separately, not in result.json.
        if parsed.get('data'):
            j=self.out/'embedded.json'; j.write_text(json.dumps(parsed['data'],ensure_ascii=False,indent=2))
            files.append(str(j))
        return self.done(route,source or pageurl,files,parsed,extra)
    def done(self,route,source,files,parsed=None,extra=None):
        obj={'ok':True,'route':route,'url':self.url,'source_url':source,'want':self.want,
             'files':files,'images':(parsed or {}).get('images',[]), 'media':(parsed or {}).get('media',[]),
             'attempts':self.attempts,'fetched_at':dt.datetime.now(dt.timezone.utc).isoformat(),
             'archived':route.startswith(('Wayback','archive.today','Arctic Shift'))}
        if extra: obj.update(extra)
        self.result=obj; self.write_result(); return obj
    def write_result(self): (self.out/'result.json').write_text(json.dumps(self.result,ensure_ascii=False,indent=2))
    def download(self,urls,route, *, proxy=None, media=False):
        urls=list(dict.fromkeys(urls))
        if 'dribbble.com' in urlparse(self.url).netloc and not media:
            uploads=[u for u in urls if '/userupload/' in u]
            if uploads:
                urls=[u.split('?')[0] for u in uploads if not re.search(r'(?:resize=(?:400|600)|400x300)',u)] or [u.split('?')[0] for u in uploads]
        folder=self.out/('media' if media else 'images'); folder.mkdir(exist_ok=True)
        files=[]
        for url in urls[:self.limit*3]:
            if len(files)>=self.limit: break
            if urlparse(url).scheme not in ('http','https'): continue
            try:
                resp,data=fetch(url,proxy=proxy,timeout=20,max_bytes=30*1024*1024)
                if resp.status_code!=200 or not data: continue
                ct=resp.headers.get('content-type','').lower()
                if media:
                    if not (ct.startswith(('video/','audio/')) or urlparse(url).path.lower().endswith(('.m3u8','.mpd'))): continue
                elif not is_image(resp,data): continue
                name=safe_file_name(url,len(files)+1,ct); p=folder/name; p.write_bytes(data)
                files.append({'path':str(p),'source':url,'bytes':len(data)})
            except (requests.RequestException,ValueError,OSError): continue
        if files:
            manifest=folder/'sources.json'; manifest.write_text(json.dumps(files,indent=2))
            self.note(route,f'{len(files)} verified files',True)
            return self.done(route,self.url,[x['path'] for x in files]+[str(manifest)],extra={'downloaded':files})
        self.note(route,'no usable files'); return None
    def accept(self,route,status,body,final,headers=None,kind='html',is_source=False):
        verdict=check(status,body,final,headers)
        if not verdict.ok:
            self.note(route,verdict.reason); return None
        parsed=parse_page(body,final)
        if self.want=='images':
            return self.download(parsed['images'],route)
        if self.want=='media':
            return self.download(parsed['media'],route,media=True)
        if self.want=='html' and kind!='html':
            self.note(route,'real text but not raw HTML'); self.partial.append((route,body,final,kind)); return None
        self.note(route,f'content ({verdict.text_chars} chars)',True)
        return self.save(route,body,source=final,kind=kind,parsed=parsed)
    def request(self,route,url, *, headers=None, proxy=None, timeout=20, kind=None):
        if url in self.seen and proxy is None and headers is None: return None
        if proxy is None and headers is None: self.seen.add(url)
        try:
            r,data=fetch(url,headers=headers,proxy=proxy,timeout=timeout)
            if r.headers.get('content-type','').lower().startswith('image/') and self.want=='images':
                return self.download([url],route,proxy=proxy)
            if route.startswith('plain fetch') and (urlparse(r.url).hostname or '').split('.')[-2:] != (urlparse(self.url).hostname or '').split('.')[-2:]:
                self.note(route,'redirected to unrelated '+str(urlparse(r.url).hostname)); return None
            body=decode(data,r)
            return self.accept(route,r.status_code,body,r.url,r.headers,kind=kind or ('html' if '<html' in body[:4000].lower() else 'text'))
        except (requests.RequestException,ValueError,OSError) as exc:
            self.note(route,str(exc)); return None

    def plain(self):
        for n,h in enumerate((HEADERS,dict(HEADERS,**{'User-Agent':'Googlebot/2.1 (+http://www.google.com/bot.html)'})),1):
            r=self.request('plain fetch'+(' retry' if n==2 else ''),self.url,headers=h)
            if r:return r
        return None
    def reader(self):
        hdr={'Accept':'text/plain','X-Return-Format':'html' if self.want=='html' else 'markdown','X-With-Images-Summary':'true'}
        if os.getenv('JINA_API_KEY'): hdr['Authorization']='Bearer '+os.environ['JINA_API_KEY']
        target='https://r.jina.ai/'+self.url
        return self.request('r.jina.ai reader',target,headers=hdr,timeout=35,kind='html' if self.want=='html' else 'text')

    def site_sources(self):
        url=self.url; p=urlparse(url); host=(p.hostname or '').lower(); paths=[]
        if host.endswith(('x.com','twitter.com')):
            paths += [('X oEmbed', 'https://publish.twitter.com/oembed?'+urlencode({'url':url})),]
            mid=re.search(r'/status/(\d+)',p.path)
            if mid: paths.insert(0,('X syndication JSON','https://cdn.syndication.twimg.com/tweet-result?id='+mid.group(1)+'&token=4'))
        if host.endswith('reddit.com'):
            base=url.rstrip('/').replace('old.reddit.com','www.reddit.com')
            paths += [('Reddit .json',base+'/.json'),('old Reddit',base.replace('www.reddit.com','old.reddit.com')+'/')]
        if host.endswith('instagram.com') and '/p/' in p.path:
            paths.append(('Instagram oEmbed','https://www.instagram.com/api/v1/oembed/?url='+quote(url,safe='')))
        if host.endswith('youtube.com') or host.endswith('youtu.be'):
            paths.append(('YouTube oEmbed','https://www.youtube.com/oembed?'+urlencode({'url':url,'format':'json'})))
        if host.endswith('vimeo.com'):
            paths.append(('Vimeo oEmbed','https://vimeo.com/api/oembed.json?url='+quote(url,safe='')))
        if p.path and not p.path.endswith('/'): paths.append(('site ?format=json',url+('&' if '?' in url else '?')+'format=json'))
        paths.append(('site sitemap',f'{p.scheme}://{p.netloc}/sitemap.xml'))
        paths.append(('site RSS',f'{p.scheme}://{p.netloc}/feed/'))
        # Ask link preview bots for the meta tags; some sites exempt their user agents.
        bots=[{'User-Agent':'facebookexternalhit/1.1','Accept-Language':'en-US,en;q=0.9'},
              {'User-Agent':'Twitterbot/1.0','Accept-Language':'en-US,en;q=0.9'}]
        for b in bots:
            try:
                r,data=fetch(url,headers=b,timeout=12)
                body=decode(data,r); v=check(r.status_code,body,r.url,r.headers)
                if v.ok:
                    got=self.accept('site preview metadata',r.status_code,body,r.url,r.headers)
                    if got: return got
                if r.status_code in (404,410): continue
                parsed=parse_page(body,r.url)
                if self.want=='images' and parsed['images']:
                    got=self.download(parsed['images'],'site og:image');
                    if got:return got
                for typ,href in parsed['sources']:
                    if 'oembed' in typ or any(x in typ for x in ('rss','atom','sitemap')): paths.insert(0,('site linked '+typ,href))
                if parsed['data'] and self.want=='text':
                    txt=json.dumps(parsed['data'],ensure_ascii=False)
                    if len(txt)>100:
                        self.note('site JSON-LD / __NEXT_DATA__','embedded data',True)
                        return self.save('site JSON-LD / __NEXT_DATA__',txt,source=r.url,kind='text')
            except (requests.RequestException,ValueError): pass
        for name,source in paths[:14]:
            if name=='site sitemap' and self.want not in ('text','html'): continue
            try:
                r,data=fetch(source,timeout=12,max_bytes=2*1024*1024)
                body=decode(data,r)
                v=check(r.status_code,body,r.url,r.headers)
                if not v.ok: self.note(name,v.reason); continue
                if name in ('site sitemap','site RSS'):
                    # Feed/sitemap content about another page is not the requested page. Record lead only.
                    self.note(name,'available, but not the exact page; see site feed')
                    (self.out/(name.replace(' ','_')+'.xml')).write_text(body)
                    continue
                got=self.accept(name,r.status_code,body,r.url,r.headers)
                if got:return got
            except (requests.RequestException,ValueError) as e:self.note(name,str(e))
        return None

    def media_route(self):
        if self.no_media or not shutil.which('yt-dlp'):return None
        # --dump-json gives metadata without downloading large video.
        command=['yt-dlp','--no-playlist','--skip-download','--dump-single-json','--socket-timeout','20','--retries','1',self.url]
        try:
            p=run_bounded(command,timeout=55)
            if p.returncode: self.note('yt-dlp metadata',(p.stderr or 'no metadata')[-250:]);return None
            meta=json.loads(p.stdout); title=meta.get('title') or ''; desc=meta.get('description') or ''
            imgs=[t.get('url') for t in meta.get('thumbnails',[]) if t.get('url')]
            txt='Title: '+title+'\nDescription: '+desc+'\nUploader: '+str(meta.get('uploader') or '')
            (self.out/'media.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
            if self.want=='images': return self.download(list(reversed(imgs)),'yt-dlp thumbnails')
            if self.want=='media':
                # Download into a bounded single-file directory, no playlist; caller explicitly asked for media.
                folder=self.out/'media'; folder.mkdir(exist_ok=True)
                cmd=['yt-dlp','--no-playlist','--max-filesize','30M','--socket-timeout','20','--retries','1','-o',str(folder/'media.%(ext)s'),self.url]
                q=run_bounded(cmd,timeout=180)
                found=[str(x) for x in folder.iterdir() if x.is_file() and x.stat().st_size>0]
                if q.returncode==0 and found:
                    self.note('yt-dlp media','saved media',True)
                    return self.done('yt-dlp media',self.url,found+[str(self.out/'media.json')],extra={'title':title})
                self.note('yt-dlp media',(q.stderr or 'download failed')[-200:]);return None
            if len(txt)>100:
                self.note('yt-dlp metadata','title/description read',True)
                return self.save('yt-dlp metadata',txt,kind='text',extra={'metadata':str(self.out/'media.json')})
        except (subprocess.TimeoutExpired,ValueError,OSError) as e:self.note('yt-dlp metadata',str(e))
        return None

    def archives(self):
        if self.no_cache:return None
        try:
            r,data=fetch('https://archive.org/wayback/available?'+urlencode({'url':self.url}),timeout=18)
            snap=json.loads(data).get('archived_snapshots',{}).get('closest',{})
            if snap.get('available'):
                src=snap['url'].replace('http://web.archive.org','https://web.archive.org')
                src=re.sub(r'/web/(\d+)(?:[a-z]{2}_)?/',r'/web/\1id_/',src)
                # Archive may itself rate-limit the data-centre IP; do not mislabel that as content.
                got=self.request('Wayback raw snapshot',src,timeout=25)
                if got:return got
            else:self.note('Wayback availability','no available snapshot')
        except (requests.RequestException,ValueError,KeyError) as e:self.note('Wayback availability',str(e))
        # Arctic Shift stores historical public Reddit submissions. It is a mirror, not the live post.
        host=(urlparse(self.url).hostname or '').lower()
        if host.endswith('reddit.com'):
            m=re.search(r'/comments/([a-z0-9]+)/',urlparse(self.url).path)
            if m:
                mirror='https://arctic-shift.photon-reddit.com/api/posts/ids?ids='+m.group(1)
                try:
                    resp,data=fetch(mirror,timeout=15)
                    obj=json.loads(data)
                    rows=obj.get('data',[])
                    if resp.status_code==200 and rows and rows[0].get('id')==m.group(1):
                        post=rows[0]
                        text='Title: '+str(post.get('title',''))+'\nAuthor: '+str(post.get('author',''))+'\nBody: '+str(post.get('selftext',''))+'\nOriginal: '+self.url
                        if len(text)>100:
                            self.note('Arctic Shift public Reddit archive','historical submission (not live comments)',True)
                            return self.save('Arctic Shift public Reddit archive',text,source=mirror,kind='text',extra={'archived':True})
                except (requests.RequestException,ValueError,KeyError) as e:self.note('Arctic Shift public Reddit archive',str(e))
        # archive.today often challenges datacentre clients; it is a lookup, not a guaranteed path.
        try:
            lookup='https://archive.ph/newest/'+self.url
            got=self.request('archive.today lookup',lookup,timeout=18)
            if got:return got
        except Exception as e:self.note('archive.today lookup',str(e))
        return None

    def browser(self,*,paid=False):
        if self.no_browser:return None
        if paid and not (os.getenv('PROXY_URL') or os.getenv('CAPSOLVER_API_KEY') or os.getenv('TWOCAPTCHA_API_KEY')):return None
        src=Path(__file__).with_name('browser_fetch.mjs')
        if not shutil.which('node'):self.note('browser','Node unavailable');return None
        cmd=['node',str(src),self.url,'--out',str(self.out/'browser'),'--wait',str(self.wait)]
        if self.storage: cmd+=['--storage',self.storage]
        if self.save_state: cmd+=['--save-state']
        if paid:
            # PROXY_URL stays in the child environment, never in the process command line.
            if os.getenv('CAPSOLVER_API_KEY') or os.getenv('TWOCAPTCHA_API_KEY'):cmd+=['--solve']
        env=dict(os.environ)
        if not paid: env.pop('PROXY_URL',None);env.pop('CAPSOLVER_API_KEY',None);env.pop('TWOCAPTCHA_API_KEY',None)
        name='browser' + (' (optional paid)' if paid else '')
        try:
            p=run_bounded(cmd,env=env,timeout=self.wait+65)
            j=json.loads(p.stdout.strip().splitlines()[-1]);
            if not j.get('ok'):
                self.note(name,j.get('reason','no content'));return None
            text=Path(j['text_file']).read_text()
            html_path=Path(j['html']); body=html_path.read_text()
            if self.want=='images':
                return self.download([x['url'] for x in j['images']],name,proxy=os.getenv('PROXY_URL') if paid else None)
            if self.want=='media':
                return self.download(j['media'],name,proxy=os.getenv('PROXY_URL') if paid else None,media=True)
            self.note(name,f"rendered {j['text_chars']} chars; screenshot {j['screenshot']}",True)
            return self.save(name,body if self.want=='html' else text,source=j['final_url'],kind=self.want,
                             extra={'screenshot':j['screenshot'],'browser':str(self.out/'browser'/'browser.json')})
        except (subprocess.TimeoutExpired,ValueError,KeyError,OSError) as e:self.note(name,str(e));return None

    def run(self):
        # Media extraction goes first only when explicitly requested; avoids slow browser for video links.
        if (self.want=='media' or self.want=='text' and any(x in (urlparse(self.url).hostname or '') for x in ('youtube.com','youtu.be','tiktok.com'))) and any(x in (urlparse(self.url).hostname or '') for x in SOCIAL):
            if self.media_route():return self.result
        for route in (self.plain,self.reader,self.site_sources):
            if route():return self.result
        if self.want in ('text','images') and any(x in (urlparse(self.url).hostname or '') for x in SOCIAL):
            if self.media_route():return self.result
        for route in (self.archives,lambda:self.browser(paid=False),lambda:self.browser(paid=True)):
            if route():return self.result
        if self.want=='media' and self.media_route():return self.result
        if self.partial and self.want=='text':
            name,body,src,kind=self.partial[0]; self.note(name+' partial','only this usable text was found',True)
            return self.save(name+' partial',body,source=src,kind=kind)
        self.result={'ok':False,'url':self.url,'want':self.want,'attempts':self.attempts,
                     'next':'No real content found. Ask for the exact URL, a user-provided copy, or a saved login/browser session. Do not ask for a password. Do not call a captcha page a result.'}
        self.write_result(); return self.result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('url');ap.add_argument('--want',choices=['text','html','images','media'],default='text')
    ap.add_argument('--out',default='./unblock-out');ap.add_argument('--limit',type=int,default=8)
    ap.add_argument('--wait',type=int,default=25,help='seconds to let browser challenge clear')
    ap.add_argument('--no-browser',action='store_true');ap.add_argument('--no-cache',action='store_true')
    ap.add_argument('--no-media',action='store_true');ap.add_argument('--storage',help='your own Playwright storage state for a login')
    ap.add_argument('--save-state',action='store_true',help='save browser cookies in output (keep private)')
    a=ap.parse_args()
    try:r=Ladder(a.url,a.want,a.out,wait=a.wait,limit=a.limit,no_browser=a.no_browser,no_cache=a.no_cache,
                 no_media=a.no_media,storage=a.storage,save_state=a.save_state).run()
    except ValueError as e:ap.error(str(e))
    print(json.dumps({'ok':r['ok'],'route':r.get('route'),'files':r.get('files'),'result':str(Path(a.out)/'result.json')},ensure_ascii=False))
    sys.exit(0 if r['ok'] else 2)

if __name__=='__main__':main()
