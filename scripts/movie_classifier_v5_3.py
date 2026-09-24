from pathlib import Path
import json, re
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT = BASE_DIR / "data" / "movie_v51_result.json"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

RULES = [
("邵氏武侠",["邵氏武侠","shaw wuxia","celestial wuxia"]),
("邵氏功夫",["邵氏功夫","shaw kung fu","celestial kung fu"]),
("邵氏动作",["邵氏动作","shaw action","celestial action"]),
("邵氏恐怖",["邵氏恐怖","shaw horror","celestial horror"]),
("邵氏经典",["邵氏经典","shaw classic","celestial classic"]),
("邵氏综合",["邵氏","shaw brothers","shaw movies","celestial movies","celestial"]),
("香港电影",["香港电影","香港片","hong kong movie","hong kong movies","hong kong film","hk movie","hk movies","mei ah movie","meiah movie"]),
("粤语电影",["粤语电影","粵語電影","粤语片","粵語片","cantonese movie","cantonese film"]),
("功夫电影",["功夫电影","功夫片","kung fu","kungfu","martial arts"]),
("武侠电影",["武侠电影","武俠電影","武侠片","武俠片","wuxia"]),
("恐怖电影",["恐怖电影","恐怖片","horror movie","horror movies","horror film","horror films","horror"]),
("惊悚电影",["惊悚电影","驚悚電影","惊悚片","驚悚片","thriller movie","thriller movies","thriller film","thriller films","thriller"]),
("经典电影",["经典电影","經典電影","经典片","經典片","classic movie","classic movies","classic film","classic films"]),
("老电影",["老电影","老電影","old movie","old movies","old film","old films"]),
("怀旧电影",["怀旧","懷舊","nostalgia","retro movie","retro movies","retro film"]),
("动作电影",["动作电影","動作電影","动作片","動作片","action movie","action movies","action film","action films"]),
("犯罪电影",["犯罪电影","犯罪片","crime movie","crime movies","crime film","crime films"]),
("西部电影",["西部电影","西部片","western movie","western movies","western film","western films"]),
("喜剧电影",["喜剧电影","喜劇電影","喜剧片","喜劇片","comedy movie","comedy movies","comedy film","comedy films"]),
("剧情电影",["剧情电影","劇情電影","剧情片","劇情片","drama movie","drama movies","drama film","drama films"]),
]
EXCLUDE=["tv","series","channel","news","radio","music","sports","weather","kids","cartoon","documentary","documentaries"]

def norm(v): return re.sub(r"\s+"," ",str(v or "")).strip()
def blob(r):
    return norm(" | ".join(r.get(k,"") for k in ("name","alt","group","tvg_id","tvg_name"))).lower()

def classify(r):
    b=blob(r)
    for cat, kws in RULES:
        for kw in kws:
            if kw.lower() in b:
                return cat, kw
    return "电影综合",""

def write_m3u(path, items, default_group):
    with path.open("w",encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for r in items:
            url=norm(r.get("url") or r.get("playlist_url"))
            if not url: continue
            name=norm(r.get("name") or r.get("tvg_name") or "未命名")
            group=norm(r.get("group") or default_group)
            f.write(f'#EXTINF:-1 group-title="{group}",{name}\n{url}\n')

def main():
    if not INPUT.exists():
        print("ERROR: input not found:", INPUT); raise SystemExit(1)
    raw=json.loads(INPUT.read_text(encoding="utf-8"))
    rows=raw if isinstance(raw,list) else (raw.get("results") or raw.get("items") or raw.get("data") or [])
    final=[r for r in rows if r.get("final_ok",True)]
    out=[]; counts=Counter(); rules=Counter()
    for r in final:
        x=dict(r); cat,rule=classify(x)
        x["v53_category"]=cat; x["v53_rule"]=rule
        out.append(x); counts[cat]+=1
        if rule: rules[f"{cat} <- {rule}"]+=1

    result={"version":"V5.3","input_rows":len(rows),"final_ok_rows":len(final),
            "classification_counts":dict(counts),"rule_hits":dict(rules),"results":out}
    (DATA_DIR/"movie_v53_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (DATA_DIR/"movie_v53_summary.json").write_text(json.dumps({
        "version":"V5.3","input_rows":len(rows),"final_ok_rows":len(final),
        "classification_counts":dict(counts),"rule_hits":dict(rules),
        "note":"Classification only; no HTTP/deep/FFprobe retest."
    },ensure_ascii=False,indent=2),encoding="utf-8")

    for cat in counts:
        write_m3u(OUTPUT_DIR/f"{cat}.m3u",[x for x in out if x["v53_category"]==cat],cat)
    write_m3u(OUTPUT_DIR/"movies_v53_all.m3u",out,"电影")

    print("=== V5.3 Movie Classifier ===")
    print("Input rows:",len(rows))
    print("Final OK:",len(final))
    print("\n=== Classification ===")
    for k,v in counts.most_common(): print(f"{k}: {v}")
    print("\n=== Rule hits ===")
    for k,v in rules.most_common(40): print(f"{v:>4}  {k}")
    print("\nDone.")
    print(DATA_DIR/"movie_v53_result.json")
    print(DATA_DIR/"movie_v53_summary.json")

if __name__=="__main__": main()
