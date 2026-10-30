import os
import sys
import time
import datetime
import concurrent.futures
import pandas as pd
import requests

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Origin': 'https://machadao.com.br',
    'Referer': 'https://machadao.com.br/',
    'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site'
}

def create_session():
    if HAS_CURL_CFFI:
        try:
            s = curl_requests.Session(impersonate="chrome124")
            s.headers.update(HEADERS)
            s.get("https://machadao.com.br", timeout=15)
            return s
        except Exception:
            pass
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://machadao.com.br", timeout=15)
    except Exception:
        pass
    return s

def fetch_page(session, category, offset, page_size=20):
    cat_param = f"categories={category}&" if category else "categories=&"
    url = f"https://sense.osuper.com.br/273/1353/v2/search?brands=&{cat_param}tags=&from={offset}&size={page_size}&sortField=_score&sortOrder=desc"
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('hits', [])
            elif resp.status_code == 429:
                time.sleep(1 + attempt)
        except Exception:
            time.sleep(1)
    return []

def sync_catalog(max_workers=10):
    print("=== Coletando o catalogo MAXIMO ABSOLUTO da loja Machadao ===")
    t0 = time.time()
    main_session = create_session()

    # 1. Pega todas as categorias
    base_url = "https://sense.osuper.com.br/273/1353/v2/search?brands=&categories=&tags=&from=0&size=1&sortField=_score&sortOrder=desc"
    r = main_session.get(base_url, timeout=15)
    cats_meta = r.json().get('extraData', {}).get('categories', [])
    main_cats = [c['key'] for c in cats_meta if '>' not in c['key']]
    
    tasks = []
    page_size = 20

    print(f"Descobrindo totais das {len(main_cats)} categorias principais...")
    for cat in main_cats:
        cat_url = f"https://sense.osuper.com.br/273/1353/v2/search?brands=&categories={cat}&tags=&from=0&size=1&sortField=_score&sortOrder=desc"
        res = main_session.get(cat_url, timeout=15)
        tot = res.json().get('total', 0) if res.status_code == 200 else 0
        pages = (tot + page_size - 1) // page_size
        for p in range(pages):
            tasks.append((cat, p * page_size))

    # Coletamos tambem do endpoint geral ate 10.000 para garantir cobertura completa
    for p in range(500):
        tasks.append(("", p * page_size))

    tasks = list(set(tasks))
    print(f"Total de requisicoes planejadas: {len(tasks)} com {max_workers} threads...")

    thread_sessions = {}
    def worker(task):
        import threading
        tid = threading.get_ident()
        if tid not in thread_sessions:
            thread_sessions[tid] = create_session()
        s = thread_sessions[tid]
        cat, off = task
        return fetch_page(s, cat, off, page_size)

    all_raw_hits = []
    completed = 0
    total_tasks = len(tasks)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, t): t for t in tasks}
        for f in concurrent.futures.as_completed(futures):
            hits = f.result()
            if hits:
                all_raw_hits.extend(hits)
            completed += 1
            if completed % 100 == 0 or completed == total_tasks:
                print(f"Progresso: {completed}/{total_tasks} requisicoes concluidas ({len(all_raw_hits)} produtos brutos)...")

    print("\nDesduplicando e organizando dados...")
    seen_ids = set()
    cleaned = []

    for item in all_raw_hits:
        item_id = item.get('id') or item.get('_id')
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)

        pricing = item.get('pricing', {})
        stocking = item.get('quantity', {})
        
        name = item.get('name')
        price = pricing.get('price', 0)
        promotional_price = pricing.get('promotionalPrice')
        is_promo = pricing.get('promotion', False)
        image = item.get('image')
        store = stocking.get('inStock', 0)
        
        categories = item.get('categories', [])
        cleaned_category = "Sem Categoria"
        if categories:
            cleaned_category = categories[0].replace('store1353:', '').strip()

        red_percent = 0
        if is_promo and promotional_price and price > 0:
            red_percent = (1 - (promotional_price / price)) * 100
        
        cleaned.append({
            'name': name,
            'price': price,
            'promotionalPrice': promotional_price,
            'is_promo': is_promo,
            'red_percent': red_percent,
            'image': image,
            'store': store,
            'category': cleaned_category
        })

    df = pd.DataFrame(cleaned)
    df = df.sort_values(by=['is_promo', 'red_percent'], ascending=False).reset_index(drop=True)

    output_path = os.path.join(os.path.dirname(__file__), "produtos.parquet")
    df.to_parquet(output_path, compression="snappy")

    duration = time.time() - t0
    size_mb = os.path.getsize(output_path) / (1024 * 1024)

    print(f"\n[SUCESSO COMPLETO]")
    print(f"Total maximo de produtos unicos salvos: {len(df)}")
    print(f"Arquivo gerado: {output_path} ({size_mb:.2f} MB)")
    print(f"Tempo total: {duration:.1f} segundos")
    print(f"Data/Hora: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

if __name__ == "__main__":
    sync_catalog(max_workers=10)
