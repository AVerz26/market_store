import streamlit as st
import requests
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Ofertas Machadão", layout="wide")

st.title("🛒 Melhores Ofertas Encontradas")

@st.cache_data(ttl=3600)  # Faz o cache dos dados por 1 hora para evitar excesso de requisições
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
            
            # Filtro: Apenas produtos em promoção e com preço válido
            if pricing.get('promotion') and pricing.get('promotionalPrice'):
                name = item.get('name')
                price = pricing.get('price')
                promotional_price = pricing.get('promotionalPrice')
                image = item.get('image')
                
                # Cálculo do desconto
                red_percent = (1 - (promotional_price / price)) * 100
                
                data_for_df.append({
                    'name': name,
                    'price': price,
                    'promotionalPrice': promotional_price,
                    'red_percent': red_percent,
                    'image': image
                })
        
        return pd.DataFrame(data_for_df)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Nenhuma promoção encontrada no momento.")
else:
    # Sidebar para filtros
    st.sidebar.header("Filtros")
    min_discount = st.sidebar.slider("Desconto mínimo (%)", 0, 100, 5)
    
    # Filtrando o DF com base no slider
    df_filtered = df[df['red_percent'] >= min_discount].sort_values(by='red_percent', ascending=False)

    # Exibição em Grid (4 colunas)
    cols = st.columns(4)
    for index, row in df_filtered.iterrows():
        with cols[index % 4]:
            st.image(row['image'], use_container_width=True)
            st.markdown(f"**{row['name']}**")
            st.markdown(f"~~R$ {row['price']:.2f}~~")
            st.markdown(f"### R$ {row['promotionalPrice']:.2f}")
            st.success(f"🔥 {row['red_percent']:.0f}% de desconto")
            st.divider()
