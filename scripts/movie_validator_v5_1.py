from __future__ import annotations
import concurrent.futures, json, shutil, subprocess
from pathlib import Path
from urllib.parse import urljoin
import requests

BASE=Path(__file__).resolve().parent.parent
DATA=BASE/'data'; OUT=BASE/'output'; RESULT=DATA/'movie_test_result.json'
WORKERS=12; CT=4; RT=8; SEGMENTS=2; FF_TIMEOUT=12
CATS=['邵氏综合','邵氏武侠','邵氏功夫','邵氏动作','邵氏恐怖','邵氏经典','经典电影','老电影','香港电影','粤语电影','功夫电影','武侠电影','恐怖电影','惊悚电影','怀旧电影','电影综合']
SHAW=('邵氏','邵氏兄弟','邵氏电影','邵氏老片','shaw brothers','shaw movie','shaw movies','celestial')

def load():
    if not RESULT.exists(): raise FileNotFoundError(f'找不到 {RESULT}\n请先运行：python scripts\\movie_test_v5.py')
    x=json.loads(RESULT.read_text(encoding='utf-8'))
    if not isinstance(x,list): raise ValueError('movie_test_result.json 格式错误')
    return x

def meta(r): return ' '.join(str(r.get(k) or '') for k in ('name','alt','group','tvg_id')).lower()
def ctx(r): return ' '.join(str(r.get(k) or '') for k in ('source','playlist','playlist_url','source_url')).lower()

def classify(r):
    m=meta(r); a=m+' '+ctx(r)
    if any(x in a for x in SHAW):
        if any(x in a for x in ('邵氏武侠','shaw wuxia','wuxia')): return '邵氏武侠'
        if any(x in a for x in ('邵氏功夫','shaw kung fu','shaw kungfu','kung fu')): return '邵氏功夫'
        if any(x in a for x in ('邵氏动作','shaw action')): return '邵氏动作'
        if any(x in a for x in ('邵氏恐怖','shaw horror')): return '邵氏恐怖'
        if any(x in a for x in ('邵氏经典','shaw classic')): return '邵氏经典'
        return '邵氏综合'
    rules=[
      ('香港电影',('香港电影','hong kong movie','hong kong movies','hk movie')),
      ('粤语电影',('粤语电影','cantonese movie','cantonese movies','cantonese film')),
      ('功夫电影',('功夫电影','kung fu movie','kung fu movies','kungfu movie')),
      ('武侠电影',('武侠电影','wuxia movie','wuxia movies','wuxia film')),
      ('恐怖电影',('恐怖电影','horror movie','horror movies','horror film')),
      ('惊悚电影',('惊悚电影','thriller movie','thriller movies','thriller film')),
      ('怀旧电影',('怀旧电影','nostalgia','nostalgic movie')),
      ('老电影',('老电影','old movie','old movies','old film')),
      ('经典电影',('经典电影','classic movie','classic movies','classic film','classics'))]
    for c,terms in rules:
        if any(x in m for x in terms): return c
    return '电影综合'

def session():
    s=requests.Session(); s.headers['User-Agent']='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36'; return s

def deep_m3u8(url):
    try:
        s=session(); r=s.get(url,timeout=(CT,RT),allow_redirects=True)
        if r.status_code>=400: return False,0,'HTTP '+str(r.status_code),r.url
        text=r.content[:262144].decode('utf-8','ignore')
        if '#EXTM3U' not in text.upper(): return False,0,'not m3u8',r.url
        lines=[x.strip() for x in text.splitlines() if x.strip() and not x.startswith('#')]
        good=0
        for line in lines[:SEGMENTS]:
            u=line if line.startswith(('http://','https://')) else urljoin(r.url,line)
            try:
                sr=s.get(u,timeout=(CT,RT),stream=True,allow_redirects=True)
                if sr.status_code<400 and next(sr.iter_content(4096),b''): good+=1
                sr.close()
            except requests.RequestException: pass
        return good>0,good,'' if good else 'segments unavailable',r.url
    except requests.RequestException as e: return False,0,f'{type(e).__name__}: {e}',url

def ffprobe(url):
    if not shutil.which('ffprobe'): return None,'ffprobe not installed'
    cmd=['ffprobe','-v','error','-rw_timeout','8000000','-show_entries','stream=codec_type,codec_name,width,height','-of','json',url]
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='ignore',timeout=FF_TIMEOUT)
        if p.returncode: return False,p.stderr.strip()[:300]
        streams=json.loads(p.stdout or '{}').get('streams',[]); video=[x for x in streams if x.get('codec_type')=='video']
        return (True,json.dumps(video[0],ensure_ascii=False)) if video else (False,'no video stream')
    except subprocess.TimeoutExpired: return False,'ffprobe timeout'
    except Exception as e: return False,f'{type(e).__name__}: {e}'

def check(r):
    r=dict(r); url=str(r.get('url') or '').strip(); r['category']=classify(r); r['m3u8_deep_ok']=False; r['segment_tests']=0; r['ffprobe_ok']=None
    if not url.startswith(('http://','https://')): r['final_ok']=False; r['v51_error']='invalid URL'; return r
    if r.get('kind')=='m3u8' or url.lower().split('?',1)[0].endswith(('.m3u8','.m3u')):
        ok,n,err,fu=deep_m3u8(url); r['m3u8_deep_ok']=ok; r['segment_tests']=n; r['m3u8_error']=err; r['final_url']=fu
        if not ok: r['final_ok']=False; r['v51_error']=err; return r
    fp,info=ffprobe(url); r['ffprobe_ok']=fp; r['ffprobe_info']=info
    if fp is False: r['final_ok']=False; r['v51_error']=info; return r
    try: ms=float(r.get('elapsed_ms') or 99999)
    except: ms=99999
    r['quality_score']=5 if ms<300 else 4 if ms<800 else 3 if ms<1500 else 2 if ms<3000 else 1
    r['final_ok']=True; return r

def write(path,rows):
    lines=['#EXTM3U']
    for r in rows:
        u=r.get('final_url') or r.get('url');
        if not u: continue
        name=str(r.get('name') or r.get('alt') or 'Movie').replace('\n',' ').replace('\r',' ')
        cat=r.get('category','电影综合'); score=r.get('quality_score',0)
        lines += [f'#EXTINF:-1 group-title="{cat}",{name} [S{score}]',u]
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    DATA.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True); rows=[r for r in load() if r.get('ok')]
    unique={};
    for r in rows:
        u=str(r.get('url') or '').strip().lower().rstrip('/')
        if u: unique.setdefault(u,r)
    rows=list(unique.values()); print('=== V5.1 Deep Movie Validator ==='); print(f'HTTP alive input: {len(rows)}'); print(f'Workers: {WORKERS}\n')
    out=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        fs=[ex.submit(check,r) for r in rows]; total=len(fs)
        for i,f in enumerate(concurrent.futures.as_completed(fs),1):
            out.append(f.result())
            if i==1 or i%25==0 or i==total: print(f'Deep testing: {i}/{total}')
    final=[r for r in out if r.get('final_ok')]; final.sort(key=lambda r:(CATS.index(r['category']) if r.get('category') in CATS else 999,-int(r.get('quality_score') or 0),float(r.get('elapsed_ms') or 99999)))
    write(OUT/'movies_final.m3u',final)
    counts={c:sum(r.get('category')==c for r in final) for c in CATS}
    for c in CATS: write(OUT/f'{c}.m3u',[r for r in final if r.get('category')==c])
    summary={'unique_alive':len(rows),'deep_m3u8_ok':sum(r.get('m3u8_deep_ok') for r in out),'ffprobe_installed':shutil.which('ffprobe') is not None,'ffprobe_ok':sum(r.get('ffprobe_ok') is True for r in out),'final_ok':len(final),'categories':counts,'speed_scores':{str(s):sum(r.get('quality_score')==s for r in final) for s in range(1,6)}}
    (DATA/'movie_v51_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); (DATA/'movie_v51_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n=== V5.1 Result ==='); print(f"Unique alive: {len(rows)}"); print(f"Deep M3U8 OK: {summary['deep_m3u8_ok']}"); print(f"FFprobe installed: {summary['ffprobe_installed']}"); print(f"FFprobe OK: {summary['ffprobe_ok']}"); print(f"Final playable: {len(final)}"); print('\n=== Final categories ==='); [print(f'{c}: {counts[c]}') for c in CATS]; print('\n=== Speed scores ==='); [print(f'S{s}: {summary["speed_scores"][str(s)]}') for s in range(5,0,-1)]; print(f'\nDone. Output: {OUT}')
if __name__=='__main__': main()
