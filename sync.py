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

def sync():
    print("Iniciando sincronização dos produtos do Machadão...")
    
    # 1. Obter sessão com cookies visitando a homepage
    print("Obtendo sessão e cookies em machadao.com.br...")
    if HAS_CURL_CFFI:
        try:
            s = curl_requests.Session(impersonate="chrome124")
            s.headers.update(HEADERS)
            s.get("https://machadao.com.br", timeout=15)
        except Exception as e:
            print(f"Aviso curl_cffi: {e}, usando requests padrão.")
            s = requests.Session()
            s.headers.update(HEADERS)
            s.get("https://machadao.com.br", timeout=15)
    else:
        s = requests.Session()
        s.headers.update(HEADERS)
        s.get("https://machadao.com.br", timeout=15)
        
    # 2. Consultar catálogo completo
    url = "https://sense.osuper.com.br/273/1353/search?brands=&categories=&tags=&size=10000&from=0&search=&sortField=_score&sortOrder=desc"
    print("Consultando API do catálogo...")
    response = s.get(url, timeout=30)
    
    if response.status_code != 200:
        print(f"Erro na API: HTTP {response.status_code}")
        print(response.text[:300])
        sys.exit(1)
        
    dta = response.json()
    hits = dta.get('hits', [])
    print(f"Recebidos {len(hits)} produtos brutos da API. Processando...")
    
    data_for_df = []
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
        
        data_for_df.append({
            'name': name,
            'price': price,
            'promotionalPrice': promotional_price,
            'is_promo': is_promo,
            'red_percent': red_percent,
            'image': image,
            'store': store,
            'category': cleaned_category
        })
        
    df = pd.DataFrame(data_for_df)
    
    output_path = os.path.join(os.path.dirname(__file__), "produtos.parquet")
    df.to_parquet(output_path, compression="snappy")
    
    print(f"Sucesso! {len(df)} produtos salvos em '{output_path}'.")
    print(f"Horário da sincronização: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

if __name__ == "__main__":
    sync()
