import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title="DN솔루션즈 재무 통합 시뮬레이터", page_icon="📊", layout="wide")
st.title("DN솔루션즈 재무 통합 시뮬레이터")
st.caption("생성형 AI 활용 · 공시 기반 시나리오 · 금액 단위: 억원")
st.info("공시된 과거 실적과 사용자가 조정하는 가정을 결합한 교육·분석용 모델입니다. 2026년 산업 수주 증가율은 DN솔루션즈의 실제 수주 증가율이 아닙니다.")

def money(x):
    return f"{x:,.0f}억원"

def add_fractional(arr, t, amount):
    """현금 흐름을 월별로 선형 배분. 모델 시작 전 현금 지출은 모델 밖으로 처리."""
    lo = math.floor(t)
    f = t - lo
    if 0 <= lo < len(arr):
        arr[lo] += amount * (1-f)
    if 0 <= lo+1 < len(arr):
        arr[lo+1] += amount * f

def order_model(growth, opening_backlog, lag, cost_ratio, advance_share, advance_months, dso, dpo, months=24):
    # 2024년 신규 수주 21,331.32억원을 월평균으로 나눈 가상 주문 유입
    new_orders = [21331.32 / 12 * (1+growth/100)] * months
    revenue = [0.0] * months
    backlog = [0.0] * months
    remaining = opening_backlog
    for i in range(months):
        # 기초 잔고는 최초 lag개월에 균등 인식된다는 가정
        from_opening = opening_backlog / lag if i < lag else 0
        from_new = new_orders[i-lag] if i >= lag else 0
        revenue[i] = from_opening + from_new
        remaining = max(0, remaining + new_orders[i] - revenue[i])
        backlog[i] = remaining

    cash_out = [0.0] * months
    cash_in = [0.0] * months
    for i, rev in enumerate(revenue):
        cost = rev * cost_ratio / 100
        add_fractional(cash_out, i-advance_months, cost * advance_share/100)
        add_fractional(cash_out, i+dpo/30, cost * (1-advance_share/100))
        add_fractional(cash_in, i+dso/30, rev)
    cumulative = []
    balance = 0
    for receipt, payment in zip(cash_in, cash_out):
        balance += receipt - payment
        cumulative.append(balance)
    return pd.DataFrame({
        "월": list(range(1, months+1)),
        "신규 수주": new_orders,
        "매출 인식": revenue,
        "수주잔고": backlog,
        "현금 지출": cash_out,
        "현금 회수": cash_in,
        "누적 순현금": cumulative
    }).set_index("월")

tabs = st.tabs(["① 수주·현금흐름", "② 매출채권·재고", "③ 환율 민감도", "④ 유동성·차환", "⑤ 종합 진단"])

with st.sidebar:
    st.header("분석 기준")
    st.write("**2024년 회사 수주 공시**")
    st.metric("신규 수주", "21,331억원")
    st.metric("기말 수주잔고", "7,498억원")
    st.metric("2025년 3월 잠정 수주잔고", "8,287억원")
    st.write("**2026년 산업 수주 증가율**")
    st.metric("2026년 1~7월", "+22.5%")
    st.caption("출처: 2025.04.10 정정 증권신고서 193·367쪽, 2026년 산업 통계는 사용자가 제공한 심층보고서.")

with tabs[0]:
    st.subheader("수주 증가 → 생산 선투입 → 매출 인식 → 현금 회수")
    st.warning("증권신고서 365쪽의 일반적인 수주→매출 인식 기간은 평균 4~6개월(대형 프로젝트 제외)입니다. 기본 5개월, 6~10개월은 지연 시나리오로 비교하세요.")
    a, b, c, d = st.columns(4)
    a.metric("2024년 신규 수주", "21,331억원")
    b.metric("2024년 말 수주잔고", "7,498억원")
    c.metric("2025년 3월 수주잔고(잠정)", "8,287억원")
    d.metric("2026년 산업 누적 수주 증가", "+22.5%")
    left, right = st.columns([1, 2])
    with left:
        growth = st.slider("가정: 회사 신규 수주 증가율 (%)", -30.0, 80.0, 22.5, 0.5)
        opening = st.slider("초기 수주잔고 (억원)", 0, 15000, 8287, 100)
        lag = st.slider("수주→매출 전환기간 (개월)", 3, 12, 5)
        cogs = st.slider("매출원가율 (%)", 45.0, 90.0, 67.7, 0.5)
        pre = st.slider("원가 중 선투입 비중 (%)", 0, 100, 65, 5)
        lead = st.slider("선투입 시점: 매출 전 (개월)", 1, 10, 3)
        order_dso = st.slider("매출채권 회수기간 (일)", 0.0, 120.0, 43.5, 0.5)
        dpo = st.slider("잔여 원가 지급유예 (일)", 0, 120, 45, 5)
    df = order_model(growth, opening, lag, cogs, pre, lead, order_dso, dpo)
    baseline = order_model(0, opening, lag, cogs, pre, lead, order_dso, dpo)
    diff = df["누적 순현금"] - baseline["누적 순현금"]
    incremental_need = max(0.0, -float(diff.min()))
    absolute_need = max(0.0, -float(df["누적 순현금"].min()))
    with right:
        x1,x2,x3 = st.columns(3)
        x1.metric("가상 연간 신규 수주", money(df["신규 수주"].iloc[0]*12))
        x2.metric("첫 12개월 매출 인식", money(df["매출 인식"].iloc[:12].sum()))
        x3.metric("최대 증분 자금부담", money(incremental_need))
        st.markdown("**월별 수주와 매출 인식**")
        st.line_chart(df[["신규 수주", "매출 인식"]])
        st.markdown("**누적 현금흐름 비교**")
        plot = pd.DataFrame({
            "수주 증가 가정": df["누적 순현금"],
            "성장률 0% 비교": baseline["누적 순현금"],
            "증분 차이": diff
        })
        st.line_chart(plot)
    st.metric("모델상 최대 누적 현금부담", money(absolute_need))
    st.dataframe(df.style.format("{:,.0f}"), use_container_width=True)
    st.caption("주의: 기초 수주잔고는 첫 전환기간에 균등 매출 인식, 신규 수주는 월별 균등 발생한다고 가정합니다. 모델 시작 전의 선투입 지출, 세금, 고정비, 투자·금융현금흐름 등은 포함하지 않습니다. 따라서 추정 부족액은 실제 조달 필요액이 아닙니다.")

with tabs[1]:
    st.subheader("매출채권 회수기간과 운전자본")
    p1,p2,p3,p4 = st.columns(4)
    p1.metric("2021년 매출채권회전율", "13.4회")
    p2.metric("2024년 매출채권회전율", "8.4회")
    p3.metric("2024년 재고자산", "4,929억원")
    p4.metric("2024년 재고회전율", "3.1회")
    q1,q2 = st.columns(2)
    with q1:
        sales_wc = st.slider("연 매출액 (억원)", 10000, 35000, 21120, 100)
        old_turn = st.slider("기준 매출채권회전율 (회)", 5.0, 20.0, 13.4, 0.1)
    with q2:
        new_turn = st.slider("비교 매출채권회전율 (회)", 5.0, 20.0, 8.4, 0.1)
        rate_wc = st.slider("가정 차입금리 (%)", 0.0, 12.0, 5.0, 0.5)
    old_days, new_days = 365/old_turn, 365/new_turn
    tied_cash = sales_wc/365*(new_days-old_days)
    r1,r2,r3,r4 = st.columns(4)
    r1.metric("기준 회수기간", f"{old_days:.1f}일")
    r2.metric("비교 회수기간", f"{new_days:.1f}일")
    r3.metric("추가 묶이는 채권", money(tied_cash))
    r4.metric("연간 금융비용 환산", money(tied_cash*rate_wc/100))
    st.bar_chart(pd.DataFrame({"회수기간(일)": [old_days, new_days]}, index=["기준", "비교"]))
    st.info("회수기간 차이 × 일평균 매출액은 매출이 동일하다는 가정하의 추가 채권 잔액입니다. 실제 현금 유출액이나 과거 매출채권 증가액과는 다릅니다.")

with tabs[2]:
    st.subheader("수출 비중을 이용한 환율 민감도")
    q1,q2 = st.columns(2)
    with q1:
        fx_sales = st.slider("기준 매출액 (억원)", 10000, 35000, 22066, 100)
        fx_op = st.slider("기준 영업이익 (억원)", 0, 9000, 4117, 10)
        export = st.slider("수출 비중 (%)", 0.0, 100.0, 80.3, 0.1)
        base_fx = st.slider("기준 원/달러 환율", 1100, 1800, 1548)
    with q2:
        new_fx = st.slider("변동 후 환율", 1000, 1900, 1340)
        linked = st.slider("수출액의 달러 연동 비율 (%)", 0, 100, 100, 5)
        offset = st.slider("원가 변동에 의한 상쇄율 (%)", 0, 100, 0, 5)
    fx_pct = new_fx/base_fx - 1
    revenue_delta = fx_sales * export/100 * linked/100 * fx_pct
    op_delta = revenue_delta*(1-offset/100)
    f1,f2,f3,f4 = st.columns(4)
    f1.metric("환율 변동률", f"{fx_pct*100:+.2f}%")
    f2.metric("매출 변동액", money(revenue_delta))
    f3.metric("영업이익 변동액", money(op_delta))
    f4.metric("시나리오 영업이익률", f"{(fx_op+op_delta)/(fx_sales+revenue_delta)*100:.2f}%")
    st.bar_chart(pd.DataFrame({
        "매출액": [fx_sales, fx_sales+revenue_delta],
        "영업이익": [fx_op, fx_op+op_delta]
    }, index=["기준", "시나리오"]))
    st.warning("2024년 수출 비중을 2025년 실적에 적용한 단순 민감도입니다. 수출액 전체가 USD 결제라는 뜻이 아니며, 통화별 노출·헤지·해외 생산원가 등은 반영하지 않습니다.")

with tabs[3]:
    st.subheader("차입금 만기와 차환 시나리오")
    st.warning("1조 2,270억원의 유동성장기부채와 77.7% 유동비율은 심층보고서의 **DN오토모티브 그룹 연결 기준**입니다. DN솔루션즈 자체 연결 기준과 혼합하면 안 됩니다.")
    d1,d2,d3 = st.columns(3)
    with d1:
        maturity = st.slider("1년 내 만기 장기부채 (억원)", 0, 20000, 12270, 100)
    with d2:
        rollover = st.slider("차환 비중 (%)", 0, 100, 70, 5)
    with d3:
        borrowing_rate = st.slider("신규 차입금리 (%)", 0.0, 12.0, 5.0, 0.5)
    refinance = maturity*rollover/100
    repayment = maturity-refinance
    i1,i2,i3,i4 = st.columns(4)
    i1.metric("만기도래 부채", money(maturity))
    i2.metric("신규 차환 필요액", money(refinance))
    i3.metric("현금 등 상환 필요액", money(repayment))
    i4.metric("차환분 단순 연 이자", money(refinance*borrowing_rate/100))
    st.bar_chart(pd.DataFrame({"금액": [refinance, repayment]}, index=["차환", "현금 등 상환"]))
    st.info("유동비율 77.7%는 단기 지급불능이나 실제 현금 부족액을 의미하지 않습니다. 만기별 차입 조건, 차환 가능성, 가용 현금은 별도 확인이 필요합니다.")

with tabs[4]:
    st.subheader("재무 의사결정 종합 진단")
    t1,t2,t3,t4 = st.columns(4)
    t1.metric("수주 증가 증분 자금부담", money(incremental_need))
    t2.metric("회수기간 변화 채권 부담", money(tied_cash))
    t3.metric("환율 변화 매출 영향", money(revenue_delta))
    t4.metric("그룹 차환 필요액", money(refinance))
    st.markdown("**산업 수주 확대 → 가상 신규 수주 → 생산·재고 선투입 → 매출 인식 → 매출채권 회수 → 자금조달 검토**")
    st.write(f"현재 가정에서 수주 증가율 **{growth:.1f}%**, 매출 전환기간 **{lag}개월**을 적용하면, 성장률 0% 시나리오 대비 최대 누적 현금흐름 감소폭은 **{money(incremental_need)}**입니다.")
    st.error("각 지표는 기준일·연결 범위·가정이 서로 다릅니다. 위 금액들을 단순 합산하여 회사의 실제 부족자금으로 해석하지 마세요.")

st.divider()
st.caption("자료: DN솔루션즈 2025.04.10 정정 증권신고서(193, 348, 365, 367, 580쪽), 2025년 연결감사보고서, 사용자가 제공한 DN솔루션즈 심층분석보고서. 수주 모형은 회사 내부 계획이나 실제 현금흐름 예측이 아닌 단순 시나리오입니다.")
