import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import pdfplumber
from datetime import datetime, timedelta
from io import BytesIO

# ===================== 頁面基礎配置 =====================
st.set_page_config(
    page_title="投資工作台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂樣式：極簡深色、大字號、長輩友好、綠升紅跌（香港規範）
st.markdown("""
<style>
    .card {background: #1e1e1e; padding: 20px; border-radius: 12px; margin-bottom: 16px;}
    .up {color: #00c853;}
    .down {color: #ff1744;}
    .neutral {color: #e0e0e0;}
    div[data-testid="stMetricLabel"] p {font-size: 16px;}
    div[data-testid="stMetricValue"] {font-size: 28px;}
    .stButton button {width: 100%; height: 50px; font-size: 18px;}
    .stTabs [data-testid="stTab"] {font-size: 18px;}
</style>
""", unsafe_allow_html=True)

# ===================== 全域數據初始化 =====================
if "stock_holdings" not in st.session_state:
    st.session_state.stock_holdings = pd.DataFrame([
        {"代碼": "00700.HK", "名稱": "騰訊控股", "股數": 100, "成本價": 320.0, "券商": "富途"}
    ])

if "option_holdings" not in st.session_state:
    st.session_state.option_holdings = pd.DataFrame([
        {"合約代碼": "AAPL 20260918 C 200", "標的": "AAPL", "類型": "Call",
         "行權價": 200, "到期日": "2026-09-18", "張數": 2, "成本價": 5.2, "券商": "盈透"}
    ])

if "cash" not in st.session_state:
    st.session_state.cash = {"港幣": 50000, "美元": 10000}

if "trade_history" not in st.session_state:
    st.session_state.trade_history = pd.DataFrame(
        columns=["日期", "代碼", "資產類型", "方向", "數量", "成交價", "手續費", "券商", "備註"]
    )

# ===================== 側邊欄導航 =====================
st.sidebar.title("📊 投資工作台")
page = st.sidebar.radio(
    "功能導航",
    ["市場概覽", "我的持倉", "交易紀錄", "分析報告"],
    label_visibility="collapsed"
)
st.sidebar.markdown("---")
st.sidebar.caption("數據延遲約15-20分鐘 | 僅供參考")
st.sidebar.caption("港股代碼可直接輸入數字，如 2399")

# ===================== 工具函數 =====================
def format_stock_code(code):
    """港股代碼自動補全：輸入2399 → 02399.HK"""
    code = code.strip().upper()
    if code.isalpha():
        return code
    if '.HK' in code:
        num_part = code.replace('.HK', '')
        if num_part.isdigit():
            num_part = num_part.zfill(5)
            return f"{num_part}.HK"
        return code
    if code.isdigit():
        code = code.zfill(5)
        return f"{code}.HK"
    return code

def get_stock_price(code):
    """獲取股票最新價格"""
    try:
        formatted_code = format_stock_code(code)
        ticker = yf.Ticker(formatted_code)
        data = ticker.history(period="2d")
        if not data.empty:
            return round(data['Close'].iloc[-1], 2)
        return 0
    except Exception:
        return 0

def get_kline_data(code, period="6mo", interval="1d"):
    """獲取K線數據"""
    try:
        formatted_code = format_stock_code(code)
        ticker = yf.Ticker(formatted_code)
        df = ticker.history(period=period, interval=interval)
        df.reset_index(inplace=True)
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        return df, formatted_code
    except Exception:
        return pd.DataFrame(), code

def plot_kline(df, title="K線圖"):
    """繪製K線圖+成交量，綠升紅跌"""
    if df.empty:
        return go.Figure()
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    fig.add_trace(go.Candlestick(
        x=df['Date'], open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name="K線",
        increasing_line_color='#00c853', decreasing_line_color='#ff1744',
        increasing_fillcolor='#00c853', decreasing_fillcolor='#ff1744'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA5'], name='MA5',
                             line=dict(color='#ffd600', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], name='MA20',
                             line=dict(color='#2979ff', width=1)), row=1, col=1)
    
    colors = ['#00c853' if close >= open else '#ff1744'
              for close, open in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'],
                         name='成交量', marker_color=colors), row=2, col=1)
    
    fig.update_layout(
        title=title, template="plotly_dark",
        height=600, showlegend=True,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(font=dict(size=14))
    )
    return fig

def get_aastocks_link(code):
    """生成AASTOCKS報價鏈接"""
    if '.HK' in code.upper():
        num = code.upper().replace('.HK', '')
        return f"https://www.aastocks.com/tc/stocks/quote/detail-quote.aspx?symbol={num}"
    return None

def export_to_excel(df):
    """導出Excel文件"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='交易紀錄')
    return output.getvalue()

# ===================== 頁面1：市場概覽 =====================
if page == "市場概覽":
    st.header("🌍 市場概覽")
    
    col1, col2, col3, col4 = st.columns(4)
    index_list = {
        "恆生指數": "^HSI",
        "恆生科技指數": "^HSTECH",
        "納斯達克": "^IXIC",
        "標普500": "^GSPC"
    }
    
    for idx, (name, code) in enumerate(index_list.items()):
        price = get_stock_price(code)
        with [col1, col2, col3, col4][idx]:
            st.metric(name, f"{price:,.2f}")
    
    st.markdown("---")
    
    st.subheader("📈 個股K線查詢")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        stock_code_input = st.text_input(
            "股票代碼",
            value="00700.HK",
            help="港股可直接輸入數字，如 2399 將自動補全為 02399.HK"
        )
    with c2:
        period = st.selectbox("週期", ["1個月", "3個月", "6個月", "1年", "5年"], index=2)
        period_map = {"1個月":"1mo", "3個月":"3mo", "6個月":"6mo", "1年":"1y", "5年":"5y"}
    with c3:
        interval = st.selectbox("級別", ["日線", "週線"], index=0)
        interval_map = {"日線":"1d", "週線":"1wk"}
    
    if st.button("查看K線", type="primary"):
        df, formatted_code = get_kline_data(
            stock_code_input,
            period_map[period],
            interval_map[interval]
        )
        if not df.empty:
            fig = plot_kline(df, f"{formatted_code} K線圖")
            st.plotly_chart(fig, use_container_width=True)
            
            aastock_link = get_aastocks_link(formatted_code)
            if aastock_link:
                st.markdown(f"🔗 [前往AASTOCKS查看實時詳細報價]({aastock_link})")
        else:
            st.error("未能獲取數據，請檢查代碼是否正確，或稍後重試")

# ===================== 頁面2：我的持倉 =====================
elif page == "我的持倉":
    st.header("💰 我的持倉")
    
    stock_df = st.session_state.stock_holdings.copy()
    stock_df['現價'] = stock_df['代碼'].apply(get_stock_price)
    stock_df['持倉市值'] = stock_df['股數'] * stock_df['現價']
    stock_df['成本市值'] = stock_df['股數'] * stock_df['成本價']
    stock_df['浮動盈虧'] = stock_df['持倉市值'] - stock_df['成本市值']
    stock_df['盈虧率'] = stock_df['浮動盈虧'] / stock_df['成本市值']
    
    total_stock_value = stock_df['持倉市值'].sum()
    total_stock_pnl = stock_df['浮動盈虧'].sum()
    
    total_cash_hkd = st.session_state.cash['港幣'] + st.session_state.cash['美元'] * 7.8
    total_asset = total_stock_value + total_cash_hkd
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("總資產 (港幣)", f"HK$ {total_asset:,.2f}")
    with c2:
        delta_str = f"{total_stock_pnl:+,.2f}"
        st.metric("股票總市值", f"HK$ {total_stock_value:,.2f}", delta=delta_str)
    with c3:
        st.metric("可用現金", f"HK$ {total_cash_hkd:,.2f}")
    
    st.markdown("---")
    
    st.subheader("📊 股票持倉")
    display_stock = stock_df.copy()
    display_stock['盈虧率'] = display_stock['盈虧率'].apply(lambda x: f"{x:.2%}")
    st.dataframe(display_stock, use_container_width=True, hide_index=True, height=220)
    
    st.markdown("---")
    
    st.subheader("📋 期權持倉")
    if not st.session_state.option_holdings.empty:
        opt_df = st.session_state.option_holdings.copy()
        opt_df['到期天數'] = opt_df['到期日'].apply(
            lambda x: (pd.to_datetime(x) - datetime.now()).days
        )
        st.dataframe(opt_df, use_container_width=True, hide_index=True, height=200)
    else:
        st.info("暫未添加期權持倉")
    
    st.markdown("---")
    
    st.subheader("💵 現金結餘")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("港幣賬戶", f"HK$ {st.session_state.cash['港幣']:,.2f}")
    with c2:
        st.metric("美元賬戶", f"US$ {st.session_state.cash['美元']:,.2f}")

# ===================== 頁面3：交易紀錄 =====================
elif page == "交易紀錄":
    st.header("📝 交易紀錄")
    
    tab1, tab2, tab3 = st.tabs(["手動錄入", "檔案匯入匯出", "歷史紀錄查詢"])
    
    with tab1:
        st.subheader("新增交易紀錄")
        c1, c2, c3 = st.columns(3)
        with c1:
            trade_date = st.date_input("交易日期", value=datetime.now())
        with c2:
            trade_code = st.text_input("股票/期權代碼", help="港股可輸入數字如 2399")
        with c3:
            asset_type = st.selectbox("資產類型", ["股票", "期權"])
        
        c4, c5, c6 = st.columns(3)
        with c4:
            direction = st.selectbox("方向", ["買入", "賣出"])
        with c5:
            quantity = st.number_input("數量", min_value=0, value=100)
        with c6:
            price = st.number_input("成交價", min_value=0.0, value=0.0, step=0.01)
        
        c7, c8 = st.columns(2)
        with c7:
            fee = st.number_input("手續費", min_value=0.0, value=0.0, step=0.01)
        with c8:
            broker = st.selectbox("券商", ["富途", "老虎", "盈透", "耀才", "其他"])
        
        remark = st.text_input("備註")
        
        if st.button("儲存紀錄", type="primary"):
            formatted_code = format_stock_code(trade_code) if asset_type == "股票" else trade_code
            new_row = {
                "日期": trade_date.strftime("%Y-%m-%d"),
                "代碼": formatted_code,
                "資產類型": asset_type,
                "方向": direction,
                "數量": quantity,
                "成交價": price,
                "手續費": fee,
                "券商": broker,
                "備註": remark
            }
            st.session_state.trade_history = pd.concat(
                [st.session_state.trade_history, pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success("紀錄已儲存")
            st.rerun()
    
    with tab2:
        st.subheader("數據匯出")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="下載 CSV 格式",
                data=st.session_state.trade_history.to_csv(index=False).encode("utf-8-sig"),
                file_name="交易紀錄.csv",
                mime="text/csv"
            )
        with col2:
            excel_data = export_to_excel(st.session_state.trade_history)
            st.download_button(
                label="下載 Excel 格式",
                data=excel_data,
                file_name="交易紀錄.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        st.markdown("---")
        st.subheader("數據匯入")
        uploaded_file = st.file_uploader(
            "上傳交易紀錄檔案",
            type=["csv", "xlsx", "xls", "pdf"],
            help="支援 CSV、Excel 及券商PDF結單"
        )
        
        if uploaded_file:
            file_name = uploaded_file.name.lower()
            try:
                if file_name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                elif file_name.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(uploaded_file)
                elif file_name.endswith('.pdf'):
                    with pdfplumber.open(uploaded_file) as pdf:
                        text = ""
                        for page in pdf.pages:
                            text += page.extract_text() + "\n"
                    st.info("PDF文字提取完成")
                    with st.expander("查看提取的PDF內容"):
                        st.text(text)
                    st.stop()
                
                st.session_state.trade_history = pd.concat(
                    [st.session_state.trade_history, df],
                    ignore_index=True
                ).drop_duplicates()
                st.success("匯入成功，已更新交易紀錄")
                st.rerun()
            except Exception as e:
                st.error(f"匯入失敗：{str(e)}，請檢查檔案格式是否正確")
    
    with tab3:
        st.subheader("歷史交易篩選")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            broker_list = st.session_state.trade_history['券商'].unique().tolist()
            broker_filter = st.multiselect("券商篩選", options=broker_list, default=broker_list)
        with c2:
            type_filter = st.multiselect("資產類型", options=["股票", "期權"], default=["股票", "期權"])
        with c3:
            code_filter = st.text_input("代碼篩選", placeholder="輸入代碼如 00700.HK")
        
        if not st.session_state.trade_history.empty:
            min_date = pd.to_datetime(st.session_state.trade_history['日期']).min()
            max_date = pd.to_datetime(st.session_state.trade_history['日期']).max()
        else:
            min_date = datetime.now()
            max_date = datetime.now()
        date_range = st.date_input("日期範圍", value=[min_date, max_date])
        
        filtered_df = st.session_state.trade_history.copy()
        if broker_filter:
            filtered_df = filtered_df[filtered_df['券商'].isin(broker_filter)]
        if type_filter:
            filtered_df = filtered_df[filtered_df['資產類型'].isin(type_filter)]
        if code_filter:
            filtered_df = filtered_df[filtered_df['代碼'].str.contains(code_filter.upper(), case=False)]
        if len(date_range) == 2:
            filtered_df['日期'] = pd.to_datetime(filtered_df['日期'])
            filtered_df = filtered_df[
                (filtered_df['日期'] >= pd.to_datetime(date_range[0])) &
                (filtered_df['日期'] <= pd.to_datetime(date_range[1]))
            ]
        
        stock_trades = filtered_df[filtered_df['資產類型'] == "股票"]
        option_trades = filtered_df[filtered_df['資產類型'] == "期權"]
        
        st.markdown("#### 📊 股票交易紀錄")
        if not stock_trades.empty:
            st.dataframe(stock_trades.sort_values('日期', ascending=False),
                        use_container_width=True, hide_index=True, height=250)
        else:
            st.caption("未有符合條件的股票交易紀錄")
        
        st.markdown("#### 📋 期權交易紀錄")
        if not option_trades.empty:
            st.dataframe(option_trades.sort_values('日期', ascending=False),
                        use_container_width=True, hide_index=True, height=200)
        else:
            st.caption("未有符合條件的期權交易紀錄")

# ===================== 頁面4：分析報告 =====================
else:
    st.header("📊 投資分析")
    
    st.subheader("資產配置")
    stock_value = st.session_state.stock_holdings.apply(
        lambda row: row['股數'] * get_stock_price(row['代碼']), axis=1
    ).sum()
    cash_hkd = st.session_state.cash['港幣'] + st.session_state.cash['美元'] * 7.8
    
    pie_data = pd.DataFrame({
        '類別': ['股票', '現金'],
        '金額': [stock_value, cash_hkd]
    })
    
    fig = go.Figure(data=[go.Pie(
        labels=pie_data['類別'], values=pie_data['金額'],
        hole=0.5, marker=dict(colors=['#2979ff', '#00c853']),
        textinfo='label+percent', textfont_size=16
    )])
    fig.update_layout(template="plotly_dark", height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    st.subheader("持倉盈虧排行")
    stock_df = st.session_state.stock_holdings.copy()
    stock_df['現價'] = stock_df['代碼'].apply(get_stock_price)
    stock_df['浮動盈虧'] = (stock_df['現價'] - stock_df['成本價']) * stock_df['股數']
    stock_df = stock_df.sort_values('浮動盈虧', ascending=False)
    
    fig2 = go.Figure()
    colors = ['#00c853' if x >= 0 else '#ff1744' for x in stock_df['浮動盈虧']]
    fig2.add_trace(go.Bar(
        x=stock_df['代碼'], y=stock_df['浮動盈虧'],
        marker_color=colors, text=stock_df['浮動盈虧'].round(2),
        textposition='outside'
    ))
    fig2.update_layout(template="plotly_dark", height=400, title="個股浮動盈虧")
    st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("---")
    st.info("後續可擴充：回報率曲線、勝率分析、最大回撤、期權希臘值計算、到期風險預警")
