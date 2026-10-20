import json,sys
stem,p,blocks,n,wrong,ortho,kinds,note=sys.argv[1:9]
open('words.jsonl','a').write(json.dumps(dict(stem=stem,page=int(p),blocks=blocks,words=int(n),wrong=int(wrong),ortho=int(ortho),kinds=kinds,note=note),ensure_ascii=False)+'\n')
