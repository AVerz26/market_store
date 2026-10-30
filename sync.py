import os
import sys
import datetime
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

def sync(max_items=1000):
    print(f"Iniciando sincronização dos produtos reais do Machadão via API v2 (até {max_items} itens)...")
    
    if HAS_CURL_CFFI:
        try:
            s = curl_requests.Session(impersonate="chrome124")
            s.headers.update(HEADERS)
            s.get("https://machadao.com.br", timeout=15)
        except Exception:
            s = requests.Session()
            s.headers.update(HEADERS)
            s.get("https://machadao.com.br", timeout=15)
    else:
        s = requests.Session()
        s.headers.update(HEADERS)
        s.get("https://machadao.com.br", timeout=15)
        
    all_data = []
    page_size = 20
    
    for offset in range(0, max_items, page_size):
        url = f"https://sense.osuper.com.br/273/1353/v2/search?brands=&categories=&tags=&from={offset}&size={page_size}&sortField=_score&sortOrder=desc"
        response = s.get(url, timeout=20)
        
        if response.status_code != 200:
            print(f"Aviso: resposta HTTP {response.status_code} na página {offset}.")
            break
            
        dta = response.json()
        hits = dta.get('hits', [])
        if not hits:
            break
            
        for item in hits:
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
            
            all_data.append({
                'name': name,
                'price': price,
                'promotionalPrice': promotional_price,
                'is_promo': is_promo,
                'red_percent': red_percent,
                'image': image,
                'store': store,
                'category': cleaned_category
            })
            
        print(f"Coletados {len(all_data)} produtos...")
        if not dta.get('hasNext', False):
            break
            
    df = pd.DataFrame(all_data)
    output_path = os.path.join(os.path.dirname(__file__), "produtos.parquet")
    df.to_parquet(output_path, compression="snappy")
    print(f"Concluído! {len(df)} produtos reais salvos em '{output_path}'.")

if __name__ == "__main__":
    sync()
