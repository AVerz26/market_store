import streamlit as st
import requests
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Ofertas e Estoque Machadão", layout="wide")

st.title("🛒 Vitrine de Ofertas com Estoque")

@st.cache_data(ttl=3600)
def load_data():
    url = "https://sense.osuper.com.br/273/1353/search?brands=&categories=&tags=&size=10000&from=0&search=&sortField=_score&sortOrder=desc"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
        'Origin': 'https://machadao.com.br',
        'Referer': 'https://machadao.com.br/'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        dta = response.json()
        
        data_for_df = []
        for item in dta.get('hits', []):
            pricing = item.get('pricing', {})
            stocking = item.get('quantity', {}) # Pegando os dados de quantidade
            
            # Filtro: Apenas produtos em promoção
            if pricing.get('promotion') and pricing.get('promotionalPrice'):
                name = item.get('name')
                price = pricing.get('price')
                promotional_price = pricing.get('promotionalPrice')
                image = item.get('image')
                store = stocking.get('inStock', 0) # Variável de estoque
                
                red_percent = (1 - (promotional_price / price)) * 100
                
                data_for_df.append({
                    'name': name,
                    'price': price,
                    'promotionalPrice': promotional_price,
                    'red_percent': red_percent,
                    'image': image,
                    'store': store
                })
        
        return pd.DataFrame(data_for_df)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Nenhuma promoção encontrada no momento.")
else:
    # Sidebar
    st.sidebar.header("Configurações de Visualização")
    min_discount = st.sidebar.slider("Desconto mínimo (%)", 0, 100, 5)
    
    # Filtro de estoque na sidebar
    apenas_com_estoque = st.sidebar.checkbox("Apenas itens com estoque disponível", value=True)
    
    # Aplicando filtros
    df_filtered = df[df['red_percent'] >= min_discount]
    if apenas_com_estoque:
        df_filtered = df_filtered[df_filtered['store'] > 0]
        
    df_filtered = df_filtered.sort_values(by='red_percent', ascending=False)

    # Exibição em Grid
    cols = st.columns(4)
    for index, (idx, row) in enumerate(df_filtered.iterrows()):
        with cols[index % 4]:
            # Badge de Desconto no topo
            st.image(row['image'], use_container_width=True)
            
            # Informações do Produto
            st.markdown(f"**{row['name']}**")
            
            # Preços
            st.caption(f"De: ~~R$ {row['price']:.2f}~~")
            st.subheader(f"R$ {row['promotionalPrice']:.2f}")
            
            # Indicadores de Desconto e Estoque
            c1, c2 = st.columns(2)
            c1.markdown(f"📉 **-{row['red_percent']:.0f}%**")
            
            # Cor do estoque: Vermelho se estiver baixo (ex: < 5)
            cor_estoque = "red" if row['store'] < 5 else "green"
            c2.markdown(f"📦 :{cor_estoque}[Estoque: {int(row['store'])}]")
            
            st.divider()
