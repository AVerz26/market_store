import os
import streamlit as st
import pandas as pd
from PIL import Image
from io import BytesIO
import requests

# curl_cffi simula a pilha TLS/JA3/JA4 e HTTP/2 de navegadores modernos contra Cloudflare
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

# Configuração da página
st.set_page_config(page_title="Catálogo Machadão", layout="wide", page_icon="🛒")

st.title("🛒 Catálogo Completo de Produtos")

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

def get_session():
    """Inicializa sessão com cookies válidos visitando a página inicial do Machadão"""
    if HAS_CURL_CFFI:
        try:
            s = curl_requests.Session(impersonate="chrome124")
            s.headers.update(HEADERS)
            s.get("https://machadao.com.br", timeout=15)
            return s, True
        except Exception:
            pass

    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://machadao.com.br", timeout=15)
    except Exception:
        pass
    return s, False

GLOBAL_SESSION, IS_CURL = get_session()

def fetch_url(url, timeout=30):
    """Executa requisição com sessão e cookies estabelecidos"""
    try:
        return GLOBAL_SESSION.get(url, timeout=timeout)
    except Exception:
        if HAS_CURL_CFFI:
            try:
                return curl_requests.get(url, headers=HEADERS, impersonate="chrome124", timeout=timeout)
            except Exception:
                pass
        return requests.get(url, headers=HEADERS, timeout=timeout)

def parse_items(hits):
    """Normaliza lista de itens da API para lista de dicionários"""
    data = []
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
        
        data.append({
            'name': name,
            'price': price,
            'promotionalPrice': promotional_price,
            'is_promo': is_promo,
            'red_percent': red_percent,
            'image': image,
            'store': store,
            'category': cleaned_category
        })
    return data

def fetch_from_api_v2(max_items=200):
    """Busca produtos na nova API v2 (https://sense.osuper.com.br/273/1353/v2/search)"""
    page_size = 20  # Limite máximo aceito pelo endpoint v2
    all_data = []
    
    for offset in range(0, max_items, page_size):
        url = f"https://sense.osuper.com.br/273/1353/v2/search?brands=&categories=&tags=&from={offset}&size={page_size}&sortField=_score&sortOrder=desc"
        response = fetch_url(url, timeout=20)
        
        if response.status_code != 200:
            if not all_data:
                raise RuntimeError(f"A API recusou a conexão (HTTP {response.status_code}).")
            break
            
        dta = response.json()
        hits = dta.get('hits', [])
        if not hits:
            break
            
        all_data.extend(parse_items(hits))
        
        if not dta.get('hasNext', False):
            break
            
    return pd.DataFrame(all_data)

@st.cache_data(ttl=3600, show_spinner="Carregando produtos...")
def load_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    parquet_path = os.path.join(base_dir, "produtos.parquet")
    
    # 1. Se existir o arquivo produtos.parquet sincronizado, carrega instantaneamente
    if os.path.exists(parquet_path):
        try:
            return pd.read_parquet(parquet_path), "produtos.parquet (offline/cache)"
        except Exception:
            pass

    # 2. Se não houver arquivo salvo, busca diretamente na API v2
    df = fetch_from_api_v2()
    return df, "API v2 ao vivo"

@st.cache_data(ttl=3600)
def compress_image_url(url):
    """Compacta imagem para 150x150px em JPEG de baixa qualidade"""
    try:
        response = fetch_url(url, timeout=5)
        if response.status_code != 200:
            return None
        img = Image.open(BytesIO(response.content))
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        if hasattr(Image, 'Resampling'):
            img = img.resize((150, 150), Image.Resampling.LANCZOS)
        else:
            img = img.resize((150, 150), Image.ANTIALIAS)
        
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=60, optimize=True)
        buffer.seek(0)
        return buffer
    except Exception:
        return None

# Carregamento dos dados
try:
    df, origem = load_data()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.info("💡 Clique no botão abaixo para tentar novamente.")
    if st.button("🔄 Tentar Novamente"):
        st.cache_data.clear()
        st.rerun()
    df = pd.DataFrame()
    origem = "Nenhuma"

if df.empty:
    st.warning("Nenhum dado encontrado.")
else:
    st.sidebar.header("Filtros e Visualização")
    
    st.sidebar.caption(f"📁 Origem dos dados: **{origem}**")
    if st.sidebar.button("🔄 Recarregar Dados"):
        st.cache_data.clear()
        st.rerun()

    ver_apenas_promo = st.sidebar.toggle("Mostrar apenas promoções", value=False)
    
    categorias_disponiveis = sorted(df['category'].dropna().unique().tolist())
    categoria_selecionada = st.sidebar.selectbox("Filtrar por Categoria", ["Todos"] + categorias_disponiveis)
    
    apenas_com_estoque = st.sidebar.checkbox("Ocultar itens sem estoque", value=False)
    
    busca = st.sidebar.text_input("Buscar produto por nome")

    df_filtered = df.copy()
    
    if ver_apenas_promo:
        df_filtered = df_filtered[df_filtered['is_promo'] == True]
    
    if categoria_selecionada != "Todos":
        df_filtered = df_filtered[df_filtered['category'] == categoria_selecionada]
        
    if apenas_com_estoque:
        df_filtered = df_filtered[df_filtered['store'] > 0]
    
    if busca:
        df_filtered = df_filtered[df_filtered['name'].str.contains(busca, case=False, na=False)]

    df_filtered = df_filtered.sort_values(by=['is_promo', 'red_percent'], ascending=False)

    total_itens = len(df_filtered)
    st.info(f"Exibindo **{total_itens}** produtos.")

    # Paginação
    itens_opcoes = [24, 48, 96, "Todos"]
    itens_por_pagina = st.sidebar.selectbox("Itens por página", itens_opcoes, index=1)

    if itens_por_pagina == "Todos":
        itens_exibidos = df_filtered
        st.caption(f"Exibindo todos os {total_itens} produtos")
    else:
        total_paginas = max(1, (total_itens + itens_por_pagina - 1) // itens_por_pagina)
        pagina_atual = st.sidebar.number_input("Página", min_value=1, max_value=total_paginas, value=1, step=1)
        inicio = (pagina_atual - 1) * itens_por_pagina
        fim = inicio + itens_por_pagina
        itens_exibidos = df_filtered.iloc[inicio:fim]
        st.caption(f"Exibindo produtos {inicio + 1} a {min(fim, total_itens)} de {total_itens} (Página {pagina_atual} de {total_paginas})")

    IMAGEM_PADRAO = "https://via.placeholder.com/150x150.png?text=Sem+Foto"

    cols = st.columns(4)
    for index, (idx, row) in enumerate(itens_exibidos.iterrows()):
        with cols[index % 4]:
            
            url_imagem = row['image']
            if not url_imagem or not isinstance(url_imagem, str) or url_imagem.strip() == "":
                st.image(IMAGEM_PADRAO, use_container_width=True)
            else:
                try:
                    imagem_compactada = compress_image_url(url_imagem)
                    if imagem_compactada:
                        st.image(imagem_compactada, use_container_width=True)
                    else:
                        st.image(url_imagem, use_container_width=True)
                except Exception:
                    st.image(IMAGEM_PADRAO, use_container_width=True)
            
            st.markdown(f"**{row['name']}**")
            st.caption(f"📁 {row['category']}")
            
            if row['is_promo']:
                st.caption(f"De: ~~R$ {row['price']:.2f}~~")
                st.subheader(f"R$ {row['promotionalPrice']:.2f}")
                st.markdown(f"📉 **-{row['red_percent']:.0f}% OFF**")
            else:
                st.subheader(f"R$ {row['price']:.2f}")
                st.write(" ")
            
            cor_estoque = "red" if row['store'] <= 0 else "green"
            texto_estoque = "Esgotado" if row['store'] <= 0 else f"Estoque: {int(row['store'])}"
            st.markdown(f"📦 :{cor_estoque}[{texto_estoque}]")
            
            st.divider()
