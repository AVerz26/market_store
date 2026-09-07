import streamlit as st
import pandas as pd
from PIL import Image
from io import BytesIO
# Importando a biblioteca que simula um navegador real para burlar o Cloudflare
from curl_cffi import requests as tls_requests

# Configuração da página
st.set_page_config(page_title="Catálogo Machadão", layout="wide", page_icon="🛒")

st.title("🛒 Catálogo Completo de Produtos")

@st.cache_data(ttl=3600)
def load_data():
    url = "https://sense.osuper.com.br/273/1353/search?brands=&categories=&tags=&size=10000&from=0&search=&sortField=_score&sortOrder=desc"
    
    headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Origin': 'https://machadao.com.br',
    'Referer': 'https://machadao.com.br/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'cross-site'
}
    
    try:
        # O parâmetro impersonate="chrome" resolve o bloqueio 403
        response = tls_requests.get(url, headers=headers, impersonate="chrome", timeout=15)
        
        if response.status_code != 200:
            st.error(f"A API recusou a conexão. Código HTTP: {response.status_code}")
            return pd.DataFrame()
            
        dta = response.json()
        
        data_for_df = []
        for item in dta.get('hits', []):
            pricing = item.get('pricing', {})
            stocking = item.get('quantity', {})
            
            name = item.get('name')
            price = pricing.get('price', 0)
            promotional_price = pricing.get('promotionalPrice')
            is_promo = pricing.get('promotion', False)
            image = item.get('image')
            store = stocking.get('inStock', 0)
            
            # Extração e limpeza da categoria
            categories = item.get('categories', [])
            cleaned_category = "Sem Categoria"
            if categories:
                cleaned_category = categories[0].replace('store1353:', '').strip()

            # Cálculo do desconto
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
        
        return pd.DataFrame(data_for_df)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def compress_image_url(url):
    """Compacta imagem para 150x150px em JPEG de baixa qualidade"""
    try:
        # Usando tls_requests aqui também caso as imagens usem a mesma proteção
        response = tls_requests.get(url, impersonate="chrome", timeout=5)
        img = Image.open(BytesIO(response.content))
        
        # Tratamento para converter PNGs com fundo transparente antes de salvar em JPEG
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Redimensionar para 150x150px
        if hasattr(Image, 'Resampling'):
            img = img.resize((150, 150), Image.Resampling.LANCZOS)
        else:
            img = img.resize((150, 150), Image.ANTIALIAS)
        
        # Salvar em memória como JPEG compactado
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=60, optimize=True)
        buffer.seek(0)
        return buffer
    except Exception:
        return None

df = load_data()

if df.empty:
    st.warning("Nenhum dado encontrado.")
else:
    st.sidebar.header("Filtros e Visualização")
    
    # 1. Filtro Principal
    ver_apenas_promo = st.sidebar.toggle("Mostrar apenas promoções", value=False)
    
    # 2. Filtro de Categoria
    categorias_disponiveis = sorted(df['category'].unique().tolist())
    categoria_selecionada = st.sidebar.selectbox("Filtrar por Categoria", ["Todos"] + categorias_disponiveis)
    
    # 3. Filtro de Estoque
    apenas_com_estoque = st.sidebar.checkbox("Ocultar itens sem estoque", value=False)
    
    # 4. Busca por nome
    busca = st.sidebar.text_input("Buscar produto por nome")

    df_filtered = df.copy()
    
    if ver_apenas_promo:
        df_filtered = df_filtered[df_filtered['is_promo'] == True]
    
    if categoria_selecionada != "Todos":
        df_filtered = df_filtered[df_filtered['category'] == categoria_selecionada]
        
    if apenas_com_estoque:
        df_filtered = df_filtered[df_filtered['store'] > 0]
    
    if busca:
        df_filtered = df_filtered[df_filtered['name'].str.contains(busca, case=False)]

    # Ordenação: Promoções primeiro, depois maior desconto
    df_filtered = df_filtered.sort_values(by=['is_promo', 'red_percent'], ascending=False)

    # --- EXIBIÇÃO ---
    st.info(f"Exibindo **{len(df_filtered)}** produtos encontrados.")

    IMAGEM_PADRAO = "https://via.placeholder.com/150x150.png?text=Sem+Foto"

    cols = st.columns(4)
    for index, (idx, row) in enumerate(df_filtered.iterrows()):
        with cols[index % 4]:
            
            # --- TRATAMENTO E VALIDAÇÃO DA IMAGEM ---
            url_imagem = row['image']
            if not url_imagem or not isinstance(url_imagem, str) or url_imagem.strip() == "":
                st.image(IMAGEM_PADRAO, use_container_width=True)
            else:
                try:
                    imagem_compactada = compress_image_url(url_imagem)
                    if imagem_compactada:
                        st.image(imagem_compactada, use_container_width=True)
                    else:
                        st.image(IMAGEM_PADRAO, use_container_width=True)
                except Exception:
                    st.image(IMAGEM_PADRAO, use_container_width=True)
            
            # --- INFORMAÇÕES DO PRODUTO ---
            st.markdown(f"**{row['name']}**")
            st.caption(f"📁 {row['category']}")
            
            # Lógica de exibição de preço
            if row['is_promo']:
                st.caption(f"De: ~~R$ {row['price']:.2f}~~")
                st.subheader(f"R$ {row['promotionalPrice']:.2f}")
                st.markdown(f"📉 **-{row['red_percent']:.0f}% OFF**")
            else:
                st.subheader(f"R$ {row['price']:.2f}")
                st.write(" ") # Espaçador para manter o alinhamento
            
            # Estoque
            cor_estoque = "red" if row['store'] <= 0 else "green"
            texto_estoque = "Esgotado" if row['store'] <= 0 else f"Estoque: {int(row['store'])}"
            st.markdown(f"📦 :{cor_estoque}[{texto_estoque}]")
            
            st.divider()
