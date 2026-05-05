import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# --- 1. 페이지 기본 설정 ---
st.set_page_config(
    page_title="지상 최고의 미국 주식 분석기",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚀 미국 주식 종합 분석 대시보드")
st.markdown("---")

# --- 2. 사이드바: 종목 검색 ---
st.sidebar.header("🔍 종목 검색")
# 사용자의 요청대로 기본 입력값은 비워두고 placeholder를 사용합니다.
ticker_input = st.sidebar.text_input("티커(Ticker) 입력", placeholder="예: AAPL, NVDA, TSLA").upper().strip()
search_button = st.sidebar.button("분석하기")

# 로직 핵심: 버튼을 눌렀고 입력값이 있다면 해당 티커를, 아니면 나스닥 지수(^IXIC)를 보여줍니다.
if search_button and ticker_input:
    target_ticker = ticker_input
    is_index = False
else:
    target_ticker = "^IXIC"  # 기본값: 나스닥 지수
    is_index = True

# --- 3. 데이터 로딩 함수 정의 (Caching 적용) ---
@st.cache_data(ttl=3600)
def get_stock_data(ticker):
    """주가 과거 데이터(1년)와 종목 기본 정보를 가져옵니다."""
    try:
        yf_ticker = yf.Ticker(ticker)

        # 주가 데이터 (1년)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        df = yf_ticker.history(start=start_date, end=end_date)

        # 재무/수급 정보 (Info)
        info = yf_ticker.info

        return df, info, None
    except Exception as e:
        return None, None, str(e)


@st.cache_data(ttl=1800)
def get_google_news(ticker, is_index=False):
    """구글 뉴스 RSS를 통해 최신 뉴스를 가져옵니다."""
    news_list = []
    try:
        # 지수일 경우 검색어를 좀 더 명확하게 설정합니다.
        search_query = "나스닥 지수" if is_index and ticker == "^IXIC" else f"{ticker} 주식"
        query = urllib.parse.quote(search_query)
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)

        for item in root.findall('.//item')[:10]:
            title = item.find('title').text if item.find('title') is not None else '제목 없음'
            link = item.find('link').text if item.find('link') is not None else '#'
            pubDate = item.find('pubDate').text if item.find('pubDate') is not None else '시간 정보 없음'
            if pubDate != '시간 정보 없음':
                try:
                    dt = datetime.strptime(pubDate, '%a, %d %b %Y %H:%M:%S %Z')
                    pubDate = dt.strftime('%Y-%m-%d %H:%M')
                except: pass
            source = item.find('source').text if item.find('source') is not None else '출처 미상'

            news_list.append({
                'title': title, 'link': link, 'publisher': source, 'pubDate': pubDate,
                'summary': '해당 뉴스의 세부 내용은 원문 링크를 클릭하여 확인해주세요.'
            })
    except Exception as e:
        print(f"뉴스 수집 중 오류: {e}")
    return news_list


# --- 4. 메인 로직 시작 ---
with st.spinner(f'{target_ticker} 데이터를 분석 중입니다...'):
    df, info, error_msg = get_stock_data(target_ticker)
    news_data = get_google_news(target_ticker, is_index)

if error_msg:
    st.error(f"데이터를 불러오는데 실패했습니다. 티커를 확인해주세요: {error_msg}")
elif df is None or df.empty:
    st.warning(f"'{target_ticker}'에 대한 주가 데이터가 없습니다.")
else:
    # 제목 표시 (나스닥 지수일 경우 별도 처리)
    display_name = "나스닥 종합지수 (NASDAQ Composite)" if target_ticker == "^IXIC" else info.get('longName', target_ticker)
    st.subheader(f"📊 {display_name} ({target_ticker}) {'기본 분석' if is_index else '종목 분석'}")

    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()

    # --- 5. 상단: 핵심 지표 섹션 ---
    # 지수는 PER/PBR 등이 없으므로 텍스트를 유동적으로 변경
    metric_title = "#### 💡 주요 지수 지표" if is_index else "#### 💡 주요 종목 지표 및 수급"
    st.markdown(metric_title)

    m1, m2, m3, m4, m5, m6 = st.columns(6)

    # 안전하게 데이터를 가져오기 위한 헬퍼 함수
    def get_val(key):
        val = info.get(key, 'N/A')
        return f"{val:.2f}" if isinstance(val, (int, float)) else val

    curr_price = info.get('currentPrice', info.get('regularMarketPreviousClose', df['Close'].iloc[-1]))
    currency = info.get('currency', '$')
    
    m1.metric("현재가", f"{currency} {curr_price:,.2f}")
    m2.metric("PER (12M)", get_val('trailingPE'))
    m3.metric("PBR", get_val('priceToBook'))
    m4.metric("PSR (12M)", get_val('priceToSalesTrailing12Months'))
    
    # 지수일 경우 수급 데이터는 큰 의미가 없으므로 N/A 처리될 가능성이 높음
    inst_own = info.get('heldPercentInstitutions', 0) * 100
    m5.metric("기관 보유 비율", f"{inst_own:.1f}%" if inst_own > 0 else "N/A")
    m6.metric("공매도 비율", get_val('shortRatio'))

    st.markdown("---")

    # --- 6. 중앙: 차트 섹션 ---
    st.markdown(f"#### 📈 주가 차트 (최근 1년)")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03,
                        subplot_titles=('Candlestick & MA', 'Volume'),
                        row_heights=[0.7, 0.3])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='MA20', line=dict(color='orange', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], name='MA60', line=dict(color='cyan', width=1.5)), row=1, col=1)

    colors = ['red' if row['Close'] >= row['Open'] else 'blue' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=colors), row=2, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False, hovermode='x unified', template='plotly_dark',
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

    # --- 7. 하단: 뉴스 섹션 ---
    st.markdown(f"#### 📰 {target_ticker} 관련 최신 뉴스")

    if news_data:
        for article in news_data:
            with st.expander(f"{article['title']} ({article['publisher']}, {article['pubDate']})"):
                st.write(f"**출처:** {article['publisher']} / **게시일:** {article['pubDate']}")
                st.markdown(f"*{article['summary']}*")
                st.markdown(f"**[기사 원문 보기]({article['link']})**")
    else:
        st.info("관련 뉴스를 찾을 수 없습니다.")