from __future__ import annotations
import concurrent.futures, json, time
from pathlib import Path
from urllib.parse import urlparse
import requests

BASE_DIR=Path(__file__).resolve().parent.parent
CANDIDATES_FILE=BASE_DIR/'data'/'movie_candidates.json'
OUTPUT_DIR=BASE_DIR/'output'; DATA_DIR=BASE_DIR/'data'
MAX_WORKERS=24; CONNECT_TIMEOUT=4; READ_TIMEOUT=7; MAX_BYTES=512*1024
VIDEO_EXTENSIONS=('.m3u8','.m3u','.mp4','.ts','.flv','.mkv','.mov','.avi','.webm')
MOVIE_CATEGORIES=['邵氏综合','邵氏武侠','邵氏功夫','邵氏动作','邵氏恐怖','邵氏经典','经典电影','老电影','香港电影','粤语电影','功夫电影','武侠电影','恐怖电影','惊悚电影','怀旧电影']

def load_candidates():
    if not CANDIDATES_FILE.exists(): raise FileNotFoundError(f'找不到 {CANDIDATES_FILE}\n请先运行：python scripts\\collector_v4_1.py')
    data=json.loads(CANDIDATES_FILE.read_text(encoding='utf-8'))
    if isinstance(data,dict):
        for k in ('candidates','items','movies','data'):
            if isinstance(data.get(k),list): data=data[k]; break
    if not isinstance(data,list): raise ValueError('movie_candidates.json 格式无法识别')
    return data

def url_of(x):
    if isinstance(x,str): return x.strip()
    for k in ('url','stream_url','stream','link'):
        if isinstance(x.get(k),str) and x[k].strip(): return x[k].strip()
    return ''

def text_of(x):
    if isinstance(x,str): return x
    return ' '.join(str(x.get(k,'')) for k in ('name','alt','group','tvg_id')).lower()

def category_of(x):
    t=text_of(x)
    groups=[('邵氏武侠',('邵氏武侠','shaw wuxia')),('邵氏功夫',('邵氏功夫','shaw kung fu','shaw kungfu')),('邵氏动作',('邵氏动作','shaw action')),('邵氏恐怖',('邵氏恐怖','shaw horror')),('邵氏经典',('邵氏经典','shaw classic')),('邵氏综合',('邵氏','shaw brothers','celestial')),
    ('经典电影',('经典电影','classic movie','classic movies','classic film')),('老电影',('老电影','old movie','old movies','old film')),('香港电影',('香港电影','hong kong movie','hong kong movies')),('粤语电影',('粤语电影','cantonese movie','cantonese movies')),('功夫电影',('功夫电影','kung fu movie','kung fu movies')),('武侠电影',('武侠电影','wuxia movie','wuxia movies')),('恐怖电影',('恐怖电影','horror movie','horror movies','horror film')),('惊悚电影',('惊悚电影','thriller movie','thriller movies','thriller film')),('怀旧电影',('怀旧电影','nostalgia','nostalgic movie'))]
    for c,terms in groups:
        if any(term in t for term in terms): return c
    return '经典电影'

def test(item):
    url=url_of(item); r=dict(item) if isinstance(item,dict) else {'name':str(item)}; r.update(url=url,category=category_of(item))
    if not url.startswith(('http://','https://')):
        r.update(ok=False,status=0,elapsed_ms=None,content_type='',kind='failed',error='非HTTP/HTTPS地址'); return r
    start=time.perf_counter()
    try:
        resp=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36'},timeout=(CONNECT_TIMEOUT,READ_TIMEOUT),stream=True,allow_redirects=True)
        sample=b''
        for chunk in resp.iter_content(8192):
            if chunk:
                sample+=chunk
                if len(sample)>=MAX_BYTES: break
        ms=round((time.perf_counter()-start)*1000); ct=resp.headers.get('Content-Type',''); s=sample.decode('utf-8',errors='ignore').lower(); path=urlparse(url).path.lower()
        if 'mpegurl' in ct.lower() or 'vnd.apple.mpegurl' in ct.lower() or '#extm3u' in s or '#extinf' in s or path.endswith(('.m3u8','.m3u')): kind='m3u8'
        elif ct.lower().startswith('video/') or path.endswith(('.mp4','.ts','.flv','.mkv','.mov','.avi','.webm')): kind='video'
        elif s.startswith('<html') or '<!doctype html' in s or 'text/html' in ct.lower(): kind='html'
        else: kind='unknown'
        ok=resp.status_code<400 and kind not in ('html','unknown')
        r.update(ok=ok,status=resp.status_code,elapsed_ms=ms,content_type=ct,bytes_read=len(sample),kind=kind,final_url=resp.url,error='' if ok else f'HTTP {resp.status_code} / {kind}')
    except Exception as e:
        r.update(ok=False,status=0,elapsed_ms=round((time.perf_counter()-start)*1000),content_type='',kind='failed',error=f'{type(e).__name__}: {e}')
    return r

def write_m3u(path,rows):
    out=['#EXTM3U']
    for r in rows:
        u=r.get('url','');
        if not u: continue
        name=str(r.get('name') or r.get('alt') or 'Unknown Movie').replace('\n',' ').replace('\r',' ')
        cat=r.get('category','电影'); out.append(f'#EXTINF:-1 group-title="{cat}",{name}'); out.append(u)
    path.write_text('\n'.join(out)+'\n',encoding='utf-8')

def main():
    OUTPUT_DIR.mkdir(exist_ok=True); DATA_DIR.mkdir(exist_ok=True)
    raw=load_candidates(); unique={}
    for x in raw:
        u=url_of(x)
        if u: unique.setdefault(u.lower().rstrip('/'),x)
    candidates=list(unique.values())
    print('=== V5 Movie Source Tester ==='); print(f'Candidates: {len(candidates)}'); print(f'Workers: {MAX_WORKERS}\n')
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        fs=[pool.submit(test,x) for x in candidates]
        for i,f in enumerate(concurrent.futures.as_completed(fs),1):
            results.append(f.result())
            if i==1 or i%25==0 or i==len(fs): print(f'Testing: {i}/{len(fs)}')
    alive=[r for r in results if r.get('ok')]; m3u8=[r for r in alive if r.get('kind')=='m3u8']; video=[r for r in alive if r.get('kind')=='video']; playable=m3u8+video
    (DATA_DIR/'movie_test_result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    write_m3u(OUTPUT_DIR/'movie_candidates.m3u',candidates); write_m3u(OUTPUT_DIR/'movie_alive.m3u',alive); write_m3u(OUTPUT_DIR/'movie_playable.m3u',playable)
    counts={c:0 for c in MOVIE_CATEGORIES}
    for r in playable: counts[r['category']]=counts.get(r['category'],0)+1
    (DATA_DIR/'movie_test_summary.json').write_text(json.dumps({'candidates':len(candidates),'alive':len(alive),'m3u8':len(m3u8),'direct_video':len(video),'playable':len(playable),'category_counts':counts},ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n=== Result ==='); print(f'Candidates: {len(candidates)}'); print(f'HTTP alive: {len(alive)}'); print(f'M3U8: {len(m3u8)}'); print(f'Direct video: {len(video)}'); print(f'Playable candidates: {len(playable)}'); print('\n=== Playable categories ===')
    for c in MOVIE_CATEGORIES: print(f'{c}: {counts.get(c,0)}')
    print(f'\nDone. Output: {OUTPUT_DIR}')
if __name__=='__main__': main()
