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

def order_model(growth, opening_backlog, lag, cost_ratio, advance_share,
                advance_months, dso, dpo, deposit_pct=0, conversion_pct=100,
                cancellation_pct=0, months=24):
    """월별 단순 시나리오. 선수금은 수주 시, 나머지는 매출 후 회수.
    계약 미전환분은 잔고에 유지되며 취소율만큼 별도 제거한다.
    """
    orders = [21331.32 / 12 * (1 + growth / 100)] * months
    rev = [0.] * months
    backlog = [0.] * months
    canceled = [0.] * months
    deposits_in = [0.] * months
    outflow = [0.] * months
    collections = [0.] * months
    deposit_liability = [0.] * months
    # 모델 시작 이전 계약의 선수금 수령 여부는 불명: 기초잔고에 선수금 적용하지 않음
    remaining = opening_backlog
    deposit_balance = 0.
    deposit_pool = [0.] * months
    for i in range(months):
        new = orders[i]
        deposits_in[i] = new * deposit_pct / 100
        deposit_pool[i] = deposits_in[i]
        # 기초잔고는 전환기간 동안 균등 도래. 신규 수주는 lag개월 후 도래.
        due_opening = opening_backlog / lag if i < lag else 0.
        due_new = orders[i-lag] if i >= lag else 0.
        due = due_opening + due_new
        recognized = due * conversion_pct / 100
        canceled[i] = due * cancellation_pct / 100
        rev[i] = recognized
        remaining = max(0., remaining + new - recognized - canceled[i])
        backlog[i] = remaining
        # 매출로 전환된 신규 주문에 한해서 선수금 차감 후 회수
        deposit_applied = due_new * conversion_pct/100 * deposit_pct/100
        # 취소 주문에 대한 선수금은 즉시 환급한다는 가정
        refund = due_new * cancellation_pct/100 * deposit_pct/100
        deposits_in[i] -= refund
        deposit_balance += deposits_in[i] - deposit_applied
        deposit_liability[i] = max(0., deposit_balance)
        add_fractional(collections, i+dso/30, max(0., recognized-deposit_applied))
        cost = recognized * cost_ratio / 100
        add_fractional(outflow, i-advance_months, cost * advance_share/100)
        add_fractional(outflow, i+dpo/30, cost * (1-advance_share/100))
    balance = 0.
    cum = []
    for j in range(months):
        balance += deposits_in[j] + collections[j] - outflow[j]
        cum.append(balance)
    return pd.DataFrame({
        "월": range(1, months+1), "신규 수주": orders,
        "매출 인식": rev, "미전환 포함 수주잔고": backlog,
        "취소 수주": canceled, "선수금 순유입": deposits_in,
        "매출대금 회수": collections, "현금 지출": outflow,
        "선수금 잔액(모형)": deposit_liability, "누적 순현금": cum
    }).set_index("월")

OVERVIEW_TEXT = '# DN솔루션즈 재무 통합 분석 프로그램 설명서\n\n## 1. 개발 배경: 수주가 증가하면 회사의 현금도 바로 늘어날까?\n\nDN솔루션즈는 공작기계와 자동화 솔루션을 제조·판매하는 기업입니다. 공작기계 산업의 특징은 고객으로부터 주문을 받은 뒤 제품을 생산하고 납품하기까지 일정한 시간이 필요하다는 것입니다.\n\n2026년 국내 공작기계 산업의 1~7월 누적 수주는 전년 동기 대비 **22.5% 증가**했습니다. 반면 같은 기간 출하는 **8.1% 증가**하는 데 그쳤습니다.\n\n이는 산업 전체에서 주문이 증가하는 속도와 제품이 출하되는 속도에 차이가 있음을 보여줍니다. 다만 이 차이만으로 DN솔루션즈의 수주잔고가 같은 비율로 증가했다고 판단할 수는 없습니다.\n\n여기서 한 가지 의문이 생겼습니다.\n\n**"주문이 늘어나더라도 실제 매출과 현금이 들어오기 전까지 회사는 얼마나 많은 자금을 먼저 투입해야 할까?"**\n\n예를 들어 고객이 10억원짜리 공작기계를 주문했다고 가정하겠습니다.\n\n회사는 주문을 받았지만 아직 10억원의 매출이 발생한 것은 아닙니다. 제품을 생산하기 위해 원재료를 구매하고 인건비와 제조경비를 지출해야 합니다. 이후 제품을 납품하여 매출을 인식하더라도, 고객이 대금을 외상으로 지급한다면 현금 회수까지 추가적인 시간이 필요합니다.\n\n즉, **수주 증가 → 생산비 지출 → 매출 발생 → 매출채권 회수** 사이에는 시간차가 존재합니다.\n\n이러한 시간차가 커질수록 회사의 운전자본 부담이 증가할 수 있습니다.\n\n이에 DN솔루션즈의 증권신고서와 감사보고서를 분석하고, 생성형 AI를 활용해 수주 증가가 매출·운전자본·환율·자금조달에 미치는 영향을 확인하는 재무 통합 분석 프로그램을 구현했습니다.\n\n---\n\n## 2. 프로그램의 주요 기능\n\n### ① 수주·현금흐름 분석: 주문이 실제 현금으로 바뀌기까지\n\n첫 번째 기능은 수주가 증가했을 때 매출과 현금흐름이 언제 발생하는지를 월별로 보여주는 것입니다.\n\nDN솔루션즈의 2025년 정정 증권신고서에 따르면 2024년 신규 수주액은 약 **2조 1,331억원**, 2024년 말 수주잔고는 약 **7,498억원**입니다. 2025년 3월 잠정 수주잔고는 약 **8,287억원**으로 제시되었습니다.\n\n프로그램은 이러한 공시 수치를 출발점으로 사용합니다.\n\n사용자는 수주 증가율, 수주에서 매출로 전환되는 기간, 매출원가율, 생산비 선투입 비중, 매출채권 회수기간 등을 변경할 수 있습니다.\n\n예를 들어 수주 증가율을 22.5%, 매출 전환기간을 5개월로 설정하면, 프로그램은 가정한 신규 수주가 몇 개월 뒤 매출로 인식되는지 계산합니다.\n\n또한 매출 발생 전에 투입되는 생산비와 매출 발생 후 회수되는 현금을 각각 계산하여 월별 현금흐름 그래프로 보여줍니다.\n\n여기서 가장 중요한 지표는 **최대 증분 자금부담**입니다.\n\n이는 수주 증가율이 0%인 비교 시나리오에 비해, 수주가 증가하는 시나리오에서 누적 현금흐름이 최대 얼마만큼 악화되는지를 나타냅니다.\n\n예를 들어 신규 수주가 늘어났지만 제품을 생산하기 위한 지출이 먼저 증가하고 매출대금 회수가 늦어진다면, 프로그램은 그 기간의 현금흐름 부담을 보여줍니다.\n\n이를 통해 수주 증가가 장기적으로는 성장 기회이지만, 단기적으로는 자금조달 부담을 동반할 수 있다는 점을 확인할 수 있습니다.\n\n**재무적 의미:** 수주 증가에 맞춰 생산비 지급 일정과 매출대금 회수 일정을 함께 관리해야 합니다.\n\n### ② 매출채권·재고 분석: 매출은 같아도 현금은 부족할 수 있다\n\n두 번째 기능은 매출채권 회수속도가 운전자본에 미치는 영향을 분석합니다.\n\n기존 분석자료에 따르면 DN솔루션즈의 매출채권회전율은 2021년 13.4회에서 2024년 8.4회로 하락했습니다.\n\n매출채권회전율은 매출채권이 얼마나 빠르게 회수되는지를 보여주는 지표입니다. 이를 회수기간으로 환산하면 다음과 같습니다.\n\n- 2021년: 365일 ÷ 13.4회 = 약 27.2일\n- 2024년: 365일 ÷ 8.4회 = 약 43.5일\n\n즉, 매출채권 회수기간이 약 **16.2일 증가**한 것입니다.\n\n2024년 매출액 약 2조 1,120억원을 기준으로 매출 규모가 동일하다고 가정하면, 회수기간이 16.2일 길어지는 것만으로 약 **940억원의 추가 자금이 매출채권에 묶이는 효과**가 발생합니다.\n\n이를 연 5%의 차입금리로 조달한다고 가정하면 연간 약 47억원의 금융비용에 해당합니다.\n\n다만 이는 실제 발생한 현금 유출이나 금융비용이 아니라, 회수기간 변화가 갖는 경제적 영향을 이해하기 위한 가상 계산입니다.\n\n프로그램에서는 매출액, 회전율, 차입금리를 변경하면서 운전자본 부담이 어떻게 달라지는지 확인할 수 있습니다.\n\n또한 DN솔루션즈의 2024년 재고자산 약 4,929억원과 재고자산회전율 3.1회를 참고지표로 제시합니다.\n\n**재무적 의미:** 매출 성장뿐 아니라 매출채권 회수와 재고자산 관리가 현금흐름에 중요합니다. 재무회계 담당자는 매출채권의 회수 가능성과 대손충당금, 재고자산의 적정 평가를 함께 검토해야 합니다.\n\n### ③ 환율 민감도 분석: 수출기업의 실적은 환율에도 영향을 받는다\n\n세 번째 기능은 환율 변화가 매출액과 영업이익에 미치는 영향을 가정하여 계산합니다.\n\nDN솔루션즈는 2024년 기준 수출 비중이 약 80.3%인 기업입니다. 따라서 환율 변화는 해외 매출의 원화 환산금액에 영향을 줄 수 있습니다.\n\n예를 들어 환율이 1달러당 1,548원에서 1,340원으로 하락한다면 원화 기준 환율은 약 13.4% 하락합니다.\n\n달러에 연동되는 수출매출은 같은 외화금액을 판매하더라도 원화로 환산한 금액이 감소할 수 있습니다.\n\n프로그램은 기준 매출액, 환율, 수출 비중, 달러 연동 비율, 원가 상쇄율을 입력받아 예상 매출 및 영업이익 변동액을 계산합니다.\n\n여기서 원가 상쇄율은 환율 하락으로 수입 원재료 비용 등이 함께 감소하는 효과를 단순화한 가정입니다.\n\n주의할 점은 **수출 비중 80.3%가 모든 수출매출이 달러로 결제된다는 의미는 아니라는 것**입니다. 실제 환율 영향은 통화별 거래 비중, 환헤지, 해외 생산원가 등에 따라 달라집니다.\n\n**재무적 의미:** 해외 매출이 많은 기업은 외화자산·부채의 평가와 환율 변동에 따른 실적 영향을 함께 관리해야 합니다.\n\n### ④ 유동성·차환 분석: 필요한 자금을 어떻게 마련할 것인가?\n\n네 번째 기능은 차입금의 만기가 도래했을 때 회사가 얼마를 상환하고 얼마를 새로 조달해야 하는지 분석합니다.\n\n기존 심층분석자료에는 DN솔루션즈의 모회사인 DN오토모티브 그룹 연결 기준으로 2025년 9월 말 유동성장기부채 약 1조 2,270억원, 유동비율 77.7%가 제시되어 있습니다.\n\n이 수치는 **DN솔루션즈 자체 연결재무제표의 수치가 아니므로 별도로 구분**했습니다.\n\n유동성장기부채는 기존 장기차입금 중 1년 이내에 만기가 도래하는 금액입니다. 만기가 도래한다고 해서 반드시 전액을 보유 현금으로 상환해야 하는 것은 아닙니다. 금융기관과 협의하여 차환할 수도 있습니다.\n\n프로그램에서는 만기도래 부채, 차환 비중, 신규 차입금리를 변경할 수 있습니다.\n\n예를 들어 만기도래 부채 1조 2,270억원 중 70%를 차환한다면 다음과 같이 계산됩니다.\n\n- 차환 필요액: 8,589억원\n- 현금 등으로 상환할 금액: 3,681억원\n- 차환금리 5% 가정 시 연간 이자: 약 429억원\n\n이는 실제 회사의 상환 계획이 아니라 차환 구조를 이해하기 위한 시나리오입니다.\n\n**재무적 의미:** 재무담당자는 차입금 만기뿐 아니라 영업현금흐름, 가용 현금, 차환 가능성, 금융비용을 종합적으로 고려해야 합니다.\n\n### ⑤ 종합 진단: 개별 재무지표를 하나의 흐름으로 연결하다\n\n마지막 기능은 앞선 네 가지 분석 결과를 한 화면에 보여줍니다.\n\n수주가 증가하면 생산을 위한 선투입 자금이 늘어날 수 있습니다. 매출채권 회수가 늦어지면 현금 유입이 지연됩니다. 해외 매출 비중이 높은 상황에서 환율까지 변동하면 수익성과 현금흐름의 불확실성이 커질 수 있습니다.\n\n이러한 상황에서 차입금 만기까지 도래한다면 회사는 자금조달 계획을 더욱 면밀하게 수립해야 합니다.\n\n다만 각각의 분석은 기준일과 연결 범위가 다르므로 금액을 단순 합산해 실제 부족자금으로 해석해서는 안 됩니다.\n\n종합 진단의 목적은 정확한 미래 부족자금을 예언하는 것이 아니라, **서로 다른 재무적 위험이 어떤 경로로 연결되는지 파악하는 것**입니다.\n\n---\n\n## 3. 프로그램을 구현하며 얻은 인사이트\n\n이번 프로그램을 구현하며 가장 중요하게 느낀 점은 **매출과 이익의 증가가 반드시 현금흐름의 개선을 의미하지는 않는다는 것**입니다.\n\n특히 공작기계 산업에서는 수주 이후 생산과 납품까지 시간이 필요하기 때문에, 수주 증가가 오히려 단기적인 운전자본 부담으로 이어질 수 있습니다.\n\n또한 매출채권 회수기간이 조금만 길어져도 상당한 자금이 묶일 수 있으며, 환율 변동과 차입금 만기까지 고려하면 개별 재무지표를 독립적으로 관리하는 것만으로는 충분하지 않다는 점을 확인했습니다.\n\n재무회계 직무에서는 이러한 분석의 출발점이 되는 매출, 매출채권, 재고자산, 매입채무 및 차입금이 재무제표에 정확히 반영되도록 관리하는 것이 중요합니다.\n\n정확한 회계정보가 확보되어야 회사의 수익성과 재무건전성을 올바르게 분석하고, 경영진이 합리적인 의사결정을 내릴 수 있기 때문입니다.\n\n**궁극적으로 이번 프로그램은 재무제표에 나타난 숫자를 단순히 확인하는 것을 넘어, 숫자의 변동 원인을 이해하고 향후 발생할 수 있는 재무적 과제를 예측하는 연습이었습니다.**\n\n입사 후에도 결산과 회계처리의 정확성을 확보하는 것을 기본으로, 재무정보의 변동 원인을 분석하고 이를 경영 의사결정에 필요한 정보로 전환할 수 있는 재무 전문가로 성장하고자 합니다.'

tabs = st.tabs(["📖 개요", "① 수주·현금흐름", "② 매출채권·재고", "③ 환율 민감도", "④ 유동성·차환", "⑤ 종합 진단"])

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
    st.markdown(OVERVIEW_TEXT)

with tabs[1]:
    st.subheader("수주 증가 → 선수금 → 생산 선투입 → 매출 인식 → 현금 회수")
    st.warning("증권신고서: 일반적인 수주→매출 인식 기간은 평균 4~6개월입니다. 계약 이행 지연·취소·환율 차이로 수주잔고와 실제 매출액은 달라질 수 있습니다.")
    a,b,c,d = st.columns(4)
    a.metric("2024년 신규 수주", "21,331억원")
    b.metric("2024년 말 수주잔고", "7,498억원")
    c.metric("2025년 3월 잠정 수주잔고", "8,287억원")
    d.metric("2026년 산업 수주 증가", "+22.5%")
    left,right=st.columns([1,2])
    with left:
        growth=st.slider("가정: 회사 신규 수주 증가율 (%)",-30.0,80.0,22.5,0.5)
        opening=st.slider("초기 수주잔고 (억원)",0,15000,8287,100)
        lag=st.slider("수주→매출 전환기간 (개월)",3,12,5)
        conversion=st.slider("도래 수주 중 매출 전환율 (%)",50,100,95,5)
        cancellation=st.slider("도래 수주 중 취소율 (%)",0,30,0,1)
        if conversion+cancellation>100:
            st.error("매출 전환율과 취소율의 합은 100%를 초과할 수 없습니다.")
            st.stop()
        deposit=st.slider("신규 수주 시 선수금 수령 비율 (%)",0,70,10,5)
        cogs=st.slider("매출원가율 (%)",45.0,90.0,67.7,0.5)
        pre=st.slider("원가 중 선투입 비중 (%)",0,100,65,5)
        lead=st.slider("선투입 시점: 매출 전 (개월)",1,10,3)
        order_dso=st.slider("잔여 매출대금 회수기간 (일)",0.0,120.0,43.5,0.5)
        dpo=st.slider("잔여 원가 지급유예 (일)",0,120,45,5)
    args=(opening,lag,cogs,pre,lead,order_dso,dpo,deposit,conversion,cancellation)
    df=order_model(growth,*args)
    baseline=order_model(0,*args)
    diff=df["누적 순현금"]-baseline["누적 순현금"]
    incremental_need=max(0.,-float(diff.min()))
    absolute_need=max(0.,-float(df["누적 순현금"].min()))
    with right:
        x1,x2,x3=st.columns(3)
        x1.metric("가상 연간 신규 수주",money(df["신규 수주"].iloc[0]*12))
        x2.metric("첫 12개월 매출 인식",money(df["매출 인식"].iloc[:12].sum()))
        x3.metric("최대 증분 자금부담",money(incremental_need))
        st.markdown("**수주·매출·잔고 흐름**")
        st.line_chart(df[["신규 수주","매출 인식","미전환 포함 수주잔고"]])
        st.markdown("**현금흐름: 선수금과 매출대금 회수 분리**")
        st.line_chart(df[["선수금 순유입","매출대금 회수","현금 지출"]])
        st.markdown("**누적 현금흐름 비교**")
        st.line_chart(pd.DataFrame({"수주 증가 가정":df["누적 순현금"],"성장률 0% 비교":baseline["누적 순현금"],"증분 차이":diff}))
    st.metric("모델상 최대 누적 현금부담",money(absolute_need))
    st.dataframe(df.style.format("{:,.0f}"),use_container_width=True)
    st.caption("선수금 비율·매출 전환율·취소율은 공시된 실제 비율이 아닌 가정입니다. 미전환분은 잔고에 남고 취소분은 차감됩니다. 기초 수주잔고에 대한 과거 선수금은 알 수 없어 반영하지 않습니다. 모델 시작 전 선투입 지출과 계약별 세부 현금조건 등은 제외되므로 실제 부족자금 예측이 아닙니다.")

with tabs[2]:
    st.subheader("매출채권·재고: 회수조건과 평가효과 구분")
    p1,p2,p3,p4=st.columns(4)
    p1.metric("2024년 말 매출채권", "2,978억원")
    p2.metric("전년 대비 증가", "+47.3%")
    p3.metric("2024년 재고자산", "4,929억원")
    p4.metric("2024년 매출채권회전율", "8.4회")
    st.info("증권신고서에 따르면 2024년 매출채권 증가에는 12월 매출 집중과 외화채권 원화 평가액 증가가 영향을 주었습니다. 증가분 전체를 회수 지연으로 판단할 수 없습니다.")
    q1,q2=st.columns(2)
    with q1:
        sales_wc=st.slider("연 매출액 (억원)",10000,35000,21120,100)
        old_turn=st.slider("기준 매출채권회전율 (회)",5.0,20.0,13.4,0.1)
        new_turn=st.slider("비교 매출채권회전율 (회)",5.0,20.0,8.4,0.1)
        rate_wc=st.slider("가정 차입금리 (%)",0.0,12.0,5.0,0.5)
    with q2:
        st.markdown("**매출채권 증감 분해 (가상 입력)**")
        ar_total=st.number_input("분해할 채권 증가액 (억원)",min_value=0.0,value=955.0,step=10.0)
        sales_effect=st.number_input("매출 시점·규모 영향 (억원)",min_value=0.0,value=350.0,step=10.0)
        fx_effect=st.number_input("외화채권 평가 영향 (억원)",min_value=0.0,value=250.0,step=10.0)
        st.caption("세부 영향 금액은 공시되지 않아 입력값은 예시 가정입니다. 나머지는 회수 지연으로 확정할 수 없는 미분류 차이입니다.")
    old_days,new_days=365/old_turn,365/new_turn
    tied_cash=sales_wc/365*(new_days-old_days)
    unexplained=ar_total-sales_effect-fx_effect
    r1,r2,r3,r4=st.columns(4)
    r1.metric("기준 회수기간",f"{old_days:.1f}일")
    r2.metric("비교 회수기간",f"{new_days:.1f}일")
    r3.metric("회수기간 변화 민감도",money(tied_cash))
    r4.metric("연간 가상 금융비용",money(tied_cash*rate_wc/100))
    st.bar_chart(pd.DataFrame({"금액(억원)": [sales_effect,fx_effect,unexplained]},index=["매출 시점·규모(가정)","환율 평가(가정)","미분류 잔액"]))
    st.caption("매출채권 증가 원인 분해는 단순한 가상 배분이며 실제 회계상 변동분석이 아닙니다. DN솔루션즈는 고객별 회수기간 차등 적용 및 선수금 수령을 활용한다고 공시했습니다.")
    st.markdown("**재고 보유 정책의 양면성**")
    st.write("납기 단축을 위한 전략적 재고는 고객 대응에 도움이 될 수 있으나, 수요 부진 시 보관비용·진부화·평가손실 위험이 발생할 수 있습니다. 재고 증가를 곧바로 비효율로 해석하지 않습니다.")

with tabs[3]:
    st.subheader("통화별 수출매출 환율 민감도와 헤지 효과")
    st.info("증권신고서에 기재된 결제통화: USD, EUR, CNY, GBP, AUD, JPY. 회사는 수출·수입 통화 대응(Natural Hedge) 및 통화선도 등을 활용합니다. 통화별 실제 매출·헤지 비중은 확인되지 않아 모두 가정입니다.")
    q1,q2=st.columns(2)
    with q1:
        fx_sales=st.slider("기준 매출액 (억원)",10000,35000,22066,100)
        fx_op=st.slider("기준 영업이익 (억원)",0,9000,4117,10)
        export=st.slider("수출 비중 (%)",0.0,100.0,80.3,0.1)
        offset=st.slider("원가 변동에 의한 추가 상쇄율 (%)",0,100,0,5)
    with q2:
        natural_hedge=st.slider("Natural Hedge 상쇄 비율 (%)",0,100,20,5)
        forward_hedge=st.slider("잔여 노출에 대한 통화선도 등 헤지 비율 (%)",0,100,30,5)
        st.caption("헤지 비율은 실제 계약·평가손익을 재현하지 않는 단순 시나리오입니다.")
    st.markdown("**통화별 가정: 수출액 내 비중 및 환율 변동률**")
    currencies=[("USD",45), ("EUR",25), ("CNY",15), ("GBP",5), ("AUD",5), ("JPY",5)]
    rows=[]
    for cur,default in currencies:
        c1,c2=st.columns(2)
        with c1: weight=st.number_input(f"{cur} 수출 내 비중 (%)",0.,100.,float(default),1.,key=f"w_{cur}")
        with c2: change=st.number_input(f"{cur} 환율 변동률 (%)",-60.,100.,-5. if cur=="USD" else 0.,1.,key=f"chg_{cur}")
        rows.append((cur,weight,change))
    weight_sum=sum(w for _,w,_ in rows)
    if abs(weight_sum-100)>0.001:
        st.error(f"통화별 비중 합계가 {weight_sum:.1f}%입니다. 합계 100%로 맞춰 주세요.")
        st.stop()
    gross_delta=sum(fx_sales*export/100*w/100*change/100 for _,w,change in rows)
    revenue_delta=gross_delta
    op_delta=gross_delta*(1-natural_hedge/100)*(1-forward_hedge/100)*(1-offset/100)
    fx_pct=sum(w*change/100 for _,w,change in rows)
    f1,f2,f3,f4=st.columns(4)
    f1.metric("가중 환율 변동률",f"{fx_pct:+.2f}%")
    f2.metric("매출 환산 변화",money(revenue_delta))
    f3.metric("헤지·원가 상쇄 후 이익 영향",money(op_delta))
    f4.metric("시나리오 영업이익률",f"{(fx_op+op_delta)/(fx_sales+revenue_delta)*100:.2f}%" if fx_sales+revenue_delta>0 else "계산 불가")
    st.bar_chart(pd.DataFrame({"금액(억원)": [gross_delta,op_delta]},index=["수출매출 환산 변동(가정)","상쇄 후 영업이익 영향(가정)"]))
    st.caption("실제 통화별 결제비중, 환율 민감도, 파생상품 손익, 해외 생산원가 등을 반영하지 않은 설명용 시나리오입니다. 헤지는 원화 매출액 자체를 일정하게 보장한다는 뜻이 아닙니다.")

with tabs[4]:
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

with tabs[5]:
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
st.caption("증권신고서 보완 반영: 선수금, 수주 전환·취소, 매출채권 평가 영향, 통화별 노출 및 헤지. 각 입력은 별도 표시가 없으면 시나리오 가정입니다. | 자료: DN솔루션즈 2025.04.10 정정 증권신고서(193, 348, 365, 367, 580쪽), 2025년 연결감사보고서, 사용자가 제공한 DN솔루션즈 심층분석보고서. 수주 모형은 회사 내부 계획이나 실제 현금흐름 예측이 아닌 단순 시나리오입니다.")
