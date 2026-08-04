import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ===================== 页面基础配置 =====================
st.set_page_config(
    page_title="投资看板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式：极简深色、大字号、长辈友好
st.markdown("""
<style>
    .big-number {font-size: 32px; font-weight: 700;}
    .card {background: #1e1e1e; padding: 20px; border-radius: 12px; margin-bottom: 16px;}
    .up {color: #00c853;}
    .down {color: #ff1744;}
    .neutral {color: #e0e0e0;}
    div[data-testid="stMetricLabel"] p {font-size: 16px;}
    div[data-testid="stMetricValue"] {font-size: 28px;}
    .stButton button {width: 100%; height: 50px; font-size: 18px;}
</style>
""", unsafe_allow_html=True)

# ===================== 全局数据初始化 =====================
if "stock_holdings" not in st.session_state:
    # 示例股票持仓数据
    st.session_state.stock_holdings = pd.DataFrame([
        {"代码": "00700.HK", "名称": "腾讯控股", "股数": 100, "成本价": 320.0},
        {"代码": "AAPL", "名称": "苹果公司", "股数": 50, "成本价": 170.0}
    ])

if "option_holdings" not in st.session_state:
    # 示例期权持仓数据
    st.session_state.option_holdings = pd.DataFrame([
        {"合约代码": "AAPL 20260918 C 200", "标的": "AAPL", "类型": "Call",
         "行权价": 200, "到期日": "2026-09-18", "张数": 2, "成本价": 5.2}
    ])

if "cash" not in st.session_state:
    st.session_state.cash = {"港币": 50000, "美元": 10000}

if "trade_history" not in st.session_state:
    st.session_state.trade_history = pd.DataFrame(
        columns=["日期", "代码", "类型", "方向", "数量", "成交价", "手续费"]
    )

# ===================== 侧边栏导航 =====================
st.sidebar.title("📊 投资工作台")
page = st.sidebar.radio(
    "功能导航",
    ["市场概览", "我的持仓", "交易记录", "分析报告"],
    label_visibility="collapsed"
)
st.sidebar.markdown("---")
st.sidebar.caption("数据延迟约15-20分钟 | 仅供参考")

# ===================== 工具函数 =====================
def get_stock_price(code):
    """获取股票最新价格"""
    try:
        ticker = yf.Ticker(code)
        data = ticker.history(period="1d")
        if not data.empty:
            return round(data['Close'].iloc[-1], 2)
        return 0
    except:
        return 0

def get_kline_data(code, period="6mo", interval="1d"):
    """获取K线数据"""
    try:
        ticker = yf.Ticker(code)
        df = ticker.history(period=period, interval=interval)
        df.reset_index(inplace=True)
        # 计算均线
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        return df
    except:
        return pd.DataFrame()

def plot_kline(df, title="K线图"):
    """绘制K线图+成交量"""
    if df.empty:
        return go.Figure()
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    # K线主体
    fig.add_trace(go.Candlestick(
        x=df['Date'], open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name="K线",
        increasing_line_color='#00c853', decreasing_line_color='#ff1744'
    ), row=1, col=1)
    
    # 均线
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA5'], name='MA5',
                             line=dict(color='#ffd600', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], name='MA20',
                             line=dict(color='#2979ff', width=1)), row=1, col=1)
    
    # 成交量
    colors = ['#00c853' if close >= open else '#ff1744'
              for close, open in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'],
                         name='成交量', marker_color=colors), row=2, col=1)
    
    fig.update_layout(
        title=title, template="plotly_dark",
        height=600, showlegend=True,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10)
    )
    return fig

# ===================== 页面1：市场概览 =====================
if page == "市场概览":
    st.header("🌍 市场概览")
    
    # 大盘指数卡片
    col1, col2, col3, col4 = st.columns(4)
    index_list = {
        "恒生指数": "^HSI",
        "恒生科技": "^HSTECH",
        "纳斯达克": "^IXIC",
        "标普500": "^GSPC"
    }
    
    for idx, (name, code) in enumerate(index_list.items()):
        price = get_stock_price(code)
        prev = get_stock_price(code)  # 简化处理，实际可取前收
        with [col1, col2, col3, col4][idx]:
            st.metric(name, f"{price:,.2f}", f"{0:+.2f}%")
    
    st.markdown("---")
    
    # 自选股K线
    st.subheader("📈 个股K线查询")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        stock_code = st.text_input("股票代码", value="00700.HK",
                                   help="港股加.HK后缀，如00700.HK；美股直接输代码，如AAPL")
    with c2:
        period = st.selectbox("周期", ["1mo", "3mo", "6mo", "1y", "5y"], index=2)
    with c3:
        interval = st.selectbox("级别", ["1d", "1wk"], index=0)
    
    if st.button("查看K线", type="primary"):
        df = get_kline_data(stock_code, period, interval)
        if not df.empty:
            fig = plot_kline(df, f"{stock_code} K线图")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("未获取到数据，请检查代码是否正确")

# ===================== 页面2：我的持仓 =====================
elif page == "我的持仓":
    st.header("💰 我的持仓")
    
    # 计算实时市值与盈亏
    stock_df = st.session_state.stock_holdings.copy()
    stock_df['现价'] = stock_df['代码'].apply(get_stock_price)
    stock_df['持仓市值'] = stock_df['股数'] * stock_df['现价']
    stock_df['成本市值'] = stock_df['股数'] * stock_df['成本价']
    stock_df['浮动盈亏'] = stock_df['持仓市值'] - stock_df['成本市值']
    stock_df['盈亏率'] = stock_df['浮动盈亏'] / stock_df['成本市值']
    
    total_stock_value = stock_df['持仓市值'].sum()
    total_stock_pnl = stock_df['浮动盈亏'].sum()
    
    # 现金折算（粗略按7.8汇率）
    total_cash_hkd = st.session_state.cash['港币'] + st.session_state.cash['美元'] * 7.8
    total_asset = total_stock_value + total_cash_hkd
    
    # 总资产卡片
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("总资产(港币)", f"HK$ {total_asset:,.2f}")
    with c2:
        st.metric("股票总市值", f"HK$ {total_stock_value:,.2f}",
                  delta=f"{total_stock_pnl:+,.2f}")
    with c3:
        st.metric("可用现金", f"HK$ {total_cash_hkd:,.2f}")
    
    st.markdown("---")
    
    # 股票持仓明细
    st.subheader("📊 股票持仓")
    # 格式化显示
    display_stock = stock_df.copy()
    display_stock['盈亏率'] = display_stock['盈亏率'].apply(lambda x: f"{x:.2%}")
    st.dataframe(display_stock, use_container_width=True, hide_index=True, height=200)
    
    st.markdown("---")
    
    # 期权持仓明细
    st.subheader("📋 期权持仓")
    if not st.session_state.option_holdings.empty:
        opt_df = st.session_state.option_holdings.copy()
        opt_df['到期天数'] = opt_df['到期日'].apply(
            lambda x: (pd.to_datetime(x) - datetime.now()).days
        )
        st.dataframe(opt_df, use_container_width=True, hide_index=True, height=200)
    else:
        st.info("暂未添加期权持仓")
    
    st.markdown("---")
    
    # 现金明细
    st.subheader("💵 现金余额")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("港币账户", f"HK$ {st.session_state.cash['港币']:,.2f}")
    with c2:
        st.metric("美元账户", f"US$ {st.session_state.cash['美元']:,.2f}")

# ===================== 页面3：交易记录 =====================
elif page == "交易记录":
    st.header("📝 交易记录")
    
    tab1, tab2 = st.tabs(["手动录入", "文件导入导出"])
    
    with tab1:
        st.subheader("新增交易记录")
        c1, c2, c3 = st.columns(3)
        with c1:
            trade_date = st.date_input("交易日期", value=datetime.now())
        with c2:
            trade_code = st.text_input("股票/期权代码")
        with c3:
            trade_type = st.selectbox("资产类型", ["股票", "期权"])
        
        c4, c5, c6 = st.columns(3)
        with c4:
            direction = st.selectbox("方向", ["买入", "卖出"])
        with c5:
            quantity = st.number_input("数量", min_value=0, value=100)
        with c6:
            price = st.number_input("成交价", min_value=0.0, value=0.0, step=0.01)
        
        fee = st.number_input("手续费", min_value=0.0, value=0.0, step=0.01)
        
        if st.button("保存记录", type="primary"):
            new_row = {
                "日期": trade_date.strftime("%Y-%m-%d"),
                "代码": trade_code,
                "类型": trade_type,
                "方向": direction,
                "数量": quantity,
                "成交价": price,
                "手续费": fee
            }
            st.session_state.trade_history = pd.concat(
                [st.session_state.trade_history, pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success("记录已保存")
            st.rerun()
    
    with tab2:
        st.subheader("数据备份与恢复")
        st.caption("云端不永久保存数据，建议定期导出备份")
        
        # 导出
        st.download_button(
            label="下载全部交易记录(CSV)",
            data=st.session_state.trade_history.to_csv(index=False).encode("utf-8-sig"),
            file_name="交易记录.csv",
            mime="text/csv"
        )
        
        # 导入
        uploaded_file = st.file_uploader("上传CSV交易记录", type="csv")
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.session_state.trade_history = df
                st.success("导入成功")
                st.rerun()
            except:
                st.error("文件格式错误，请检查")
    
    st.markdown("---")
    st.subheader("历史记录")
    st.dataframe(st.session_state.trade_history, use_container_width=True, hide_index=True)

# ===================== 页面4：分析报告 =====================
else:
    st.header("📊 投资分析")
    
    # 持仓配置饼图
    st.subheader("资产配置")
    stock_value = st.session_state.stock_holdings.apply(
        lambda row: row['股数'] * get_stock_price(row['代码']), axis=1
    ).sum()
    cash_hkd = st.session_state.cash['港币'] + st.session_state.cash['美元'] * 7.8
    
    pie_data = pd.DataFrame({
        '类别': ['股票', '现金'],
        '金额': [stock_value, cash_hkd]
    })
    
    fig = go.Figure(data=[go.Pie(
        labels=pie_data['类别'], values=pie_data['金额'],
        hole=0.5, marker=dict(colors=['#2979ff', '#00c853'])
    )])
    fig.update_layout(template="plotly_dark", height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # 盈亏排行
    st.subheader("持仓盈亏排行")
    stock_df = st.session_state.stock_holdings.copy()
    stock_df['现价'] = stock_df['代码'].apply(get_stock_price)
    stock_df['浮动盈亏'] = (stock_df['现价'] - stock_df['成本价']) * stock_df['股数']
    stock_df = stock_df.sort_values('浮动盈亏', ascending=False)
    
    fig2 = go.Figure()
    colors = ['#00c853' if x >= 0 else '#ff1744' for x in stock_df['浮动盈亏']]
    fig2.add_trace(go.Bar(
        x=stock_df['代码'], y=stock_df['浮动盈亏'],
        marker_color=colors, text=stock_df['浮动盈亏'].round(2),
        textposition='outside'
    ))
    fig2.update_layout(template="plotly_dark", height=400, title="个股盈亏")
    st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("---")
    st.info("更多高级分析（收益率曲线、胜率、最大回撤、期权希腊值）可后续迭代添加")
