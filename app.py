import streamlit as st
import requests
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Ofertas Machadão", layout="wide", page_icon="🛒")

st.title("🛒 Vitrine de Ofertas e Estoque")

@st.cache_data(ttl=3600)
def load_data():
    url = "https://sense.osuper.com.br/273/1353/search?brands=&categories=&tags=&size=10000&from=0&search=&sortField=_score&sortOrder=desc"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
        'Origin': 'https://machadao.com.br',
        'Referer': 'https://machadao.com.br/'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        dta = response.json()
        
        data_for_df = []
        for item in dta.get('hits', []):
            pricing = item.get('pricing', {})
            stocking = item.get('quantity', {})
            
            # Filtro base: Apenas produtos em promoção
            if pricing.get('promotion') and pricing.get('promotionalPrice'):
                name = item.get('name')
                price = pricing.get('price')
                promotional_price = pricing.get('promotionalPrice')
                image = item.get('image')
                store = stocking.get('inStock', 0)
                
                # Extração e limpeza da categoria
                categories = item.get('categories', [])
                cleaned_category = "Sem Categoria"
                if categories:
                    cleaned_category = categories[0].replace('store1353:', '').strip()

                red_percent = (1 - (promotional_price / price)) * 100
                
                data_for_df.append({
                    'name': name,
                    'price': price,
                    'promotionalPrice': promotional_price,
                    'red_percent': red_percent,
                    'image': image,
                    'store': store,
                    'category': cleaned_category
                })
        
        return pd.DataFrame(data_for_df)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Nenhuma promoção encontrada ou erro na conexão.")
else:
    # --- SIDEBAR / FILTROS ---
    st.sidebar.header("Filtros de Busca")
    
    # 1. Filtro de Categoria
    categorias_disponiveis = sorted(df['category'].unique().tolist())
    opcoes_categoria = ["Todos"] + categorias_disponiveis
    categoria_selecionada = st.sidebar.selectbox("Escolha uma Categoria", opcoes_categoria)
    
    # 2. Filtro de Desconto
    min_discount = st.sidebar.slider("Desconto mínimo (%)", 0, 100, 5)
    
    # 3. Filtro de Estoque
    apenas_com_estoque = st.sidebar.checkbox("Apenas com estoque disponível", value=True)
    
    # --- APLICANDO OS FILTROS ---
    df_filtered = df.copy()
    
    if categoria_selecionada != "Todos":
        df_filtered = df_filtered[df_filtered['category'] == categoria_selecionada]
        
    df_filtered = df_filtered[df_filtered['red_percent'] >= min_discount]
    
    if apenas_com_estoque:
        df_filtered = df_filtered[df_filtered['store'] > 0]
        
    df_filtered = df_filtered.sort_values(by='red_percent', ascending=False)

    # --- EXIBIÇÃO ---
    st.write(f"Exibindo **{len(df_filtered)}** produtos em promoção.")

    cols = st.columns(4)
    for index, (idx, row) in enumerate(df_filtered.iterrows()):
        with cols[index % 4]:
            st.image(row['image'], use_container_width=True)
            
            # Nome e Categoria (em tamanho menor)
            st.markdown(f"**{row['name']}**")
            st.caption(f"📁 {row['category']}")
            
            # Preços
            st.caption(f"De: ~~R$ {row['price']:.2f}~~")
            st.subheader(f"R$ {row['promotionalPrice']:.2f}")
            
            # Métricas de Desconto e Estoque
            c1, c2 = st.columns(2)
            c1.markdown(f"📉 **-{row['red_percent']:.0f}%**")
            
            cor_estoque = "red" if row['store'] < 3 else "green"
            c2.markdown(f"📦 :{cor_estoque}[Qtd: {int(row['store'])}]")
            
            st.divider()
