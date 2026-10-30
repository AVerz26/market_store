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

def fetch_page(session, offset, page_size=20):
    url = f"https://sense.osuper.com.br/273/1353/v2/search?brands=&categories=&tags=&from={offset}&size={page_size}&sortField=_score&sortOrder=desc"
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                return offset, data.get('hits', [])
            elif resp.status_code == 429:
                time.sleep(1 + attempt)
        except Exception:
            time.sleep(1)
    return offset, []

def sync_catalog(target_count=10000, max_workers=8):
    print(f"=== Iniciando sincronizacao acelerada de {target_count} produtos ===")
    t0 = time.time()
    
    page_size = 20
    total_pages = (target_count + page_size - 1) // page_size
    offsets = [i * page_size for i in range(total_pages)]
    
    print(f"Total de paginas a consultar: {total_pages} (lotes de {page_size}) com {max_workers} threads...")

    page_results = {}
    completed = 0
    thread_sessions = {}
    
    def worker_task(offset):
        import threading
        tid = threading.get_ident()
        if tid not in thread_sessions:
            thread_sessions[tid] = create_session()
        s = thread_sessions[tid]
        return fetch_page(s, offset, page_size)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker_task, off): off for off in offsets}
        
        for future in concurrent.futures.as_completed(futures):
            offset, hits = future.result()
            page_results[offset] = hits
            completed += 1
            if completed % 50 == 0 or completed == total_pages:
                items_so_far = sum(len(h) for h in page_results.values())
                print(f"Progresso: {completed}/{total_pages} paginas concluidas (~{items_so_far} produtos coletados)...")

    all_hits = []
    for off in sorted(page_results.keys()):
        all_hits.extend(page_results[off])

    print(f"Processando {len(all_hits)} itens brutos coletados...")

    seen_ids = set()
    cleaned_data = []

    for item in all_hits:
        item_id = item.get('id') or item.get('_id')
        if item_id and item_id in seen_ids:
            continue
        if item_id:
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
        
        cleaned_data.append({
            'name': name,
            'price': price,
            'promotionalPrice': promotional_price,
            'is_promo': is_promo,
            'red_percent': red_percent,
            'image': image,
            'store': store,
            'category': cleaned_category
        })

    df = pd.DataFrame(cleaned_data)
    output_path = os.path.join(os.path.dirname(__file__), "produtos.parquet")
    df.to_parquet(output_path, compression="snappy")

    duration = time.time() - t0
    size_mb = os.path.getsize(output_path) / (1024 * 1024)

    print(f"\n[SUCESSO] Sincronizacao concluida em {duration:.1f} segundos!")
    print(f"Total de produtos salvos: {len(df)}")
    print(f"Arquivo gerado: {output_path} ({size_mb:.2f} MB)")
    print(f"Data/Hora: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

if __name__ == "__main__":
    sync_catalog(target_count=10000, max_workers=8)
