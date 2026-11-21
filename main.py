import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide")
st.title("🌱 극지식물 생육 비교 대시보드: 처리구 vs 미처리구")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
    html, body, [class*="css"] {
       font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def read_file(file):
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            df = pd.read_csv(io.BytesIO(data), encoding=enc)
            if not df.empty:
                return df
        except Exception:
            pass
    try:
        return pd.read_excel(io.BytesIO(data))
    except Exception:
        return pd.DataFrame()


def std_cols(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}

    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif k == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"

    df = df.rename(columns=rename)

    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(
                df[c].astype(str).str.replace(",", "").str.extract(r"(-?\d+\.?\d*)")[0],
                errors="coerce"
            )
            if num.notna().mean() >= 0.5:
                df[c] = num

    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]

    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = pd.to_datetime(parts[0], format="%Y%m%d") + pd.to_timedelta(parts[1].astype(int), unit="h")
        df["time"] = parsed

    return df


st.sidebar.header("📁 업로드 파일 4개")
st.sidebar.caption("환경 2개 + 생육 2개 순서로 넣으면 처리구/미처리구 비교가 가능합니다.")

file1 = st.sidebar.file_uploader("환경 데이터 1", type=["csv", "xlsx"])
file2 = st.sidebar.file_uploader("환경 데이터 2", type=["csv", "xlsx"])
file3 = st.sidebar.file_uploader("생육 데이터 1", type=["csv", "xlsx"])
file4 = st.sidebar.file_uploader("생육 데이터 2", type=["csv", "xlsx"])

env_files = []
growth_files = []

if file1 is not None:
    df = read_file(file1)
    if not df.empty:
        df = std_cols(df)
        env_files.append(("환경1", df))

if file2 is not None:
    df = read_file(file2)
    if not df.empty:
        df = std_cols(df)
        env_files.append(("환경2", df))

if file3 is not None:
    df = read_file(file3)
    if not df.empty:
        df = std_cols(df)
        growth_files.append(("생육1", df))

if file4 is not None:
    df = read_file(file4)
    if not df.empty:
        df = std_cols(df)
        growth_files.append(("생육2", df))


def get_merged(df_list):
    frames = [df for _, df in df_list if not df.empty]
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


env_merged = get_merged(env_files)
growth_merged = get_merged(growth_files)

school_name = ""
if env_files:
    for name, df in env_files:
        if not df.empty and "time" in df.columns:
            school_name = name
            break

st.sidebar.divider()
growth_metrics = st.sidebar.multiselect(
    "생육 측정 항목",
    ["평균 생중량", "평균 잎 수", "평균 지상부 길이", "평균 지하부 길이"],
    default=["평균 생중량"],
)

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

with tab1:
    try:
        st.header("🌱 연구 배경 및 목적")
        st.write("극지 식물은 낮은 기온과 짧은 생장기 등 혹독한 환경에서 자랍니다. 이 대시보드는 미생물 처리구와 미처리구의 환경·생육 차이를 비교하는 도구입니다.")
        st.write("학교마다 측정 항목이 다를 수 있어, 업로드한 파일의 열 이름을 자동으로 표준화해 사용합니다.")

        st.subheader("📊 데이터 요약")
        summary_rows = []

        if env_merged is not None and not env_merged.empty:
            period = ""
            if "time" in env_merged.columns:
                times = env_merged["time"].dropna()
                if len(times) > 0:
                    period = f"{times.min().strftime('%Y-%m-%d')} ~ {times.max().strftime('%Y-%m-%d')}"
            cols = [c for c in ["temperature", "humidity", "ph", "ec", "co2", "water_temp"] if c in env_merged.columns]
            summary_rows.append(["환경 데이터", school_name or "학교명", f"{len(env_merged)}행", period, ", ".join(cols)])

        if growth_merged is not None and not growth_merged.empty:
            cols = [c for c in ["개체번호", "잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"] if c in growth_merged.columns]
            n_ind = growth_merged["개체번호"].nunique() if "개체번호" in growth_merged.columns else 0
            summary_rows.append(["생육 데이터", school_name or "학교명", f"{len(growth_merged)}행", f"{n_ind}개체", ", ".join(cols)])

        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows, columns=["데이터", "학교", "행 수", "기간", "측정 항목"]), width="stretch")
        else:
            st.info("아직 업로드된 파일이 없습니다.")

        st.subheader("📈 주요 지표 카드")
        total_ind = 0
        avg_temp = None
        avg_hum = None
        avg_bio = None

        if growth_merged is not None and not growth_merged.empty and "개체번호" in growth_merged.columns:
            total_ind = growth_merged["개체번호"].nunique()

        if env_merged is not None and not env_merged.empty and "temperature" in env_merged.columns:
            avg_temp = env_merged["temperature"].dropna().mean()

        if env_merged is not None and not env_merged.empty and "humidity" in env_merged.columns:
            avg_hum = env_merged["humidity"].dropna().mean()

        if growth_merged is not None and not growth_merged.empty and "생중량" in growth_merged.columns:
            avg_bio = growth_merged["생중량"].dropna().mean()

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("총 개체수", f"{total_ind}개체" if total_ind > 0 else "—")
        with c2:
            st.metric("평균 온도", f"{avg_temp:.1f}°C" if avg_temp is not None else "—")
        with c3:
            st.metric("평균 습도", f"{avg_hum:.1f}%" if avg_hum is not None else "—")
        with c4:
            st.metric("평균 생중량", f"{avg_bio:.2f}g" if avg_bio is not None else "—")

        if growth_merged is not None and not growth_merged.empty and "생중량" in growth_merged.columns:
            st.subheader("🔬 처리구별 평균 생중량 비교")
            bio = growth_merged["생중량"].dropna()
            if len(bio) >= 4:
                q25 = bio.quantile(0.25)
                q75 = bio.quantile(0.75)
                bio["처리 그룹"] = "미처리구"
                if "미생물" in str(growth_merged.columns).lower() or "처리" in str(growth_merged.columns).lower():
                    pass

                group_rows = []
                for col in growth_merged.columns:
                    if "처리" in str(col) or "group" in str(col).lower():
                        group_rows.append(col)
                        break

                if group_rows:
                    grp_col = group_rows[0]
                    if grp_col in growth_merged.columns:
                        grp = growth_merged[[grp_col, "생중량"]].dropna()
                        if len(grp) >= 2:
                            grp_summary = grp.groupby(grp_col)["생중량"].agg(["count", "mean", "min", "max"]).reset_index()
                            grp_summary.columns = ["처리 그룹", "개체 수", "평균 생중량", "최소 생중량", "최대 생중량"]
                            st.dataframe(grp_summary, width="stretch")

                            fig = px.bar(
                                grp_summary,
                                x="처리 그룹",
                                y="평균 생중량",
                                title="처리구별 평균 생중량 비교",
                                text_auto=".2f"
                            )
                            fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                            st.plotly_chart(fig, width="stretch")

                            if len(grp) >= 4:
                                q = grp["생중량"].quantile([0.25, 0.75])
                                low = grp[grp["생중량"] <= q[0.25]]
                                high = grp[grp["생중량"] >= q[0.75]]
                                if len(low) > 0 and len(high) > 0:
                                    low_avg = low["생중량"].mean()
                                    high_avg = high["생중량"].mean()
                                    st.info(f"생중량 하위 25% 평균: {low_avg:.2f}g / 상위 25% 평균: {high_avg:.2f}g")

        if env_merged is not None and not env_merged.empty:
            st.subheader("🌡️ 환경 데이터 평균 요약")
            env_rows = []
            for col in ["temperature", "humidity", "ph", "ec"]:
                if col in env_merged.columns:
                    vals = env_merged[col].dropna()
                    if len(vals) > 0:
                        env_rows.append([col, f"{vals.mean():.2f}", f"{vals.min():.2f}", f"{vals.max():.2f}"])
            if env_rows:
                st.dataframe(pd.DataFrame(env_rows, columns=["항목", "평균", "최소", "최대"]), width="stretch")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

with tab2:
    try:
        if env_merged is None or env_merged.empty:
            st.info("🌡️ 환경 데이터를 업로드하면 그래프를 볼 수 있어요.")
        else:
            st.subheader("📋 환경 데이터 요약")
            s_rows = []
            for col in ["temperature", "humidity", "ph", "ec"]:
                if col in env_merged.columns:
                    vals = env_merged[col].dropna()
                    if len(vals) > 0:
                        s_rows.append([col, f"{vals.mean():.2f}", f"{vals.min():.2f}", f"{vals.max():.2f}"])
            if s_rows:
                st.dataframe(pd.DataFrame(s_rows, columns=["항목", "평균", "최소", "최대"]), width="stretch")
            else:
                st.info("환경 데이터에 숫자 값이 없습니다.")

            st.subheader("📈 일별 환경 변화")
            if "time" in env_merged.columns:
                dft = env_merged.dropna(subset=["time"]).copy()
                if len(dft) > 0:
                    dft["date"] = dft["time"].dt.strftime("%Y-%m-%d")
                    c1, c2 = st.columns(2)
                    with c1:
                        fig = px.line(dft, x="date", y="temperature", title="온도 변화 (일별 평균)")
                        fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                        st.plotly_chart(fig, width="stretch")
                    with c2:
                        fig = px.line(dft, x="date", y="humidity", title="습도 변화 (일별 평균)")
                        fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                        st.plotly_chart(fig, width="stretch")
                    if "ph" in env_merged.columns:
                        fig = px.line(dft, x="date", y="ph", title="pH 변화 (일별 평균)")
                        fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                        st.plotly_chart(fig, width="stretch")
                    if "ec" in env_merged.columns:
                        fig = px.line(dft, x="date", y="ec", title="EC 변화 (일별 평균)")
                        fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                        st.plotly_chart(fig, width="stretch")
                else:
                    st.info("시간 정보가 없습니다.")

            with st.expander("🌱 환경 데이터 원본 + CSV 다운로드"):
                st.dataframe(env_merged, width="stretch")
                csv = env_merged.to_csv(index=False).encode("utf-8-sig")
                st.download_button("환경 데이터 다운로드", csv, file_name="환경데이터.csv", mime="text/csv")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

with tab3:
    try:
        if growth_merged is None or growth_merged.empty:
            st.info("📊 생육 데이터를 업로드하면 그래프를 볼 수 있어요.")
        else:
            st.subheader("🥇 핵심 결과 카드")
            if "생중량" in growth_merged.columns:
                bio = growth_merged["생중량"].dropna()
                if len(bio) > 0:
                    avg_b = bio.mean()
                    max_pos = bio.values.argmax()
                    min_pos = bio.values.argmin()
                    max_v = bio.max()
                    min_v = bio.min()
                    max_r = growth_merged.iloc[max_pos]
                    min_r = growth_merged.iloc[min_pos]

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("평균 생중량", f"{avg_b:.2f}g")
                    with c2:
                        st.metric("최대 생중량 개체", max_r["개체번호"], f"{max_v:.2f}g")
                    with c3:
                        st.metric("최소 생중량 개체", min_r["개체번호"], f"{min_v:.2f}g")

            st.subheader("🔬 처리구별 평균 생중량 비교")
            if growth_merged is not None and not growth_merged.empty and "생중량" in growth_merged.columns:
                bio = growth_merged["생중량"].dropna()
                if len(bio) >= 4:
                    q_low = bio.quantile(0.25)
                    q_high = bio.quantile(0.75)

                    group_candidate_cols = []
                    for c in growth_merged.columns:
                        col_lower = str(c).lower()
                        if "처리" in col_lower or "group" in col_lower or "미생물" in col_lower or "미처리" in col_lower:
                            group_candidate_cols.append(c)

                    if group_candidate_cols:
                        grp_col = group_candidate_cols[0]
                        if grp_col in growth_merged.columns:
                            grp = growth_merged[[grp_col, "생중량"]].dropna()

                            if len(grp) >= 2:
                                grp_summary = grp.groupby(grp_col)["생중량"].agg(["count", "mean", "min", "max"]).reset_index()
                                grp_summary.columns = ["처리 그룹", "개체 수", "평균 생중량", "최소 생중량", "최대 생중량"]

                                st.dataframe(grp_summary, width="stretch")

                                fig = px.bar(
                                    grp_summary,
                                    x="처리 그룹",
                                    y="평균 생중량",
                                    title="처리구별 평균 생중량 비교",
                                    text_auto=".2f"
                                )
                                fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                                st.plotly_chart(fig, width="stretch")

                                low = grp[grp["생중량"] <= q_low]
                                high = grp[grp["생중량"] >= q_high]
                                if len(low) > 0 and len(high) > 0:
                                    st.info(
                                        f"하위 25% 평균: {low['생중량'].mean():.2f}g / "
                                        f"상위 25% 평균: {high['생중량'].mean():.2f}g"
                                    )
                    else:
                        st.info("처리구 구분 열이 없습니다. 파일 첫 열 또는 '처리/그룹/미생물' 관련 열 이름을 확인하세요.")
                else:
                    st.info("생중량 데이터가 4개 이상 있어야 하위/상위 25% 비교가 가능합니다.")

            st.subheader("📊 개체별 생육 비교")
            if "개체번호" in growth_merged.columns and "생중량" in growth_merged.columns:
                gcols = ["개체번호"] + [c for c in ["잎 수", "지상부 길이", "지하부 길이", "생중량"] if c in growth_merged.columns]
                g = growth_merged[gcols].dropna().groupby("개체번호").mean().reset_index()
                g["개체번호"] = g["개체번호"].apply(lambda v: str(int(v)) if isinstance(v, float) and v.is_integer() else str(v))
                g = g.sort_values("생중량") if "생중량" in g.columns else g

                def bar_chart_metric(metric, title):
                    d = g.dropna(subset=[metric]).copy()
                    if len(d) == 0:
                        st.info(f"'{metric}' 데이터가 없어 그래프를 표시할 수 없습니다.")
                        return
                    d = d.sort_values(metric).reset_index(drop=True)
                    fig = px.bar(d, x="개체번호", y=metric, title=title)
                    fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                    if metric == "생중량" and len(d) >= 4:
                        q25 = d[metric].quantile(0.25)
                        q75 = d[metric].quantile(0.75)
                        colors = []
                        for v in d[metric]:
                            if v <= q25:
                                colors.append("#ff9999")
                            elif v >= q75:
                                colors.append("#99ff99")
                            else:
                                colors.append("#9999ff")
                        fig.update_traces(marker_color=colors)
                    st.plotly_chart(fig, width="stretch")

                selected = [m for m in ["생중량", "잎 수", "지상부 길이", "지하부 길이"] if m in g.columns and m in growth_metrics]
                if not selected:
                    selected = [m for m in ["생중량", "잎 수", "지상부 길이", "지하부 길이"] if m in g.columns]
                if not selected:
                    selected = ["생중량"]

                for m in selected:
                    if m == "생중량":
                        bar_chart_metric(m, "개체별 평균 생중량 (빨강: 하위 25%, 초록: 상위 25%)")
                    elif m == "잎 수":
                        bar_chart_metric(m, "개체별 평균 잎 수")
                    elif m == "지상부 길이":
                        bar_chart_metric(m, "개체별 평균 지상부 길이")
                    elif m == "지하부 길이":
                        bar_chart_metric(m, "개체별 평균 지하부 길이")

            st.subheader("📦 생중량 분포")
            if "생중량" in growth_merged.columns:
                bio = growth_merged["생중량"].dropna()
                if len(bio) >= 2:
                    fig = px.box(bio, y="생중량", title="생중량 분포")
                    fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("생중량 데이터가 2개 미만입니다.")

            st.subheader("📈 상관관계 분석")
            if "생중량" in growth_merged.columns and "잎 수" in growth_merged.columns:
                dc = growth_merged[["생중량", "잎 수"]].dropna()
                if len(dc) >= 2:
                    fig = px.scatter(dc, x="잎 수", y="생중량", title="잎 수 vs 생중량")
                    fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                    x = dc["잎 수"].values
                    y = dc["생중량"].values
                    coefs = np.polyfit(x, y, 1)
                    tr = np.poly1d(coefs)
                    xl = np.linspace(x.min(), x.max(), 100)
                    fig.add_trace(go.Scatter(x=xl, y=tr(xl), mode="lines", name="추세선", line=dict(color="red", dash="dash")))
                    st.plotly_chart(fig, width="stretch")
                    st.write(f"상관계수: {dc['잎 수'].corr(dc['생중량']):.3f}")
                else:
                    st.info("잎 수와 생중량 데이터가 2개 미만입니다.")

            if "생중량" in growth_merged.columns and "지상부 길이" in growth_merged.columns:
                dc = growth_merged[["생중량", "지상부 길이"]].dropna()
                if len(dc) >= 2:
                    fig = px.scatter(dc, x="지상부 길이", y="생중량", title="지상부 길이 vs 생중량")
                    fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                    x = dc["지상부 길이"].values
                    y = dc["생중량"].values
                    coefs = np.polyfit(x, y, 1)
                    tr = np.poly1d(coefs)
                    xl = np.linspace(x.min(), x.max(), 100)
                    fig.add_trace(go.Scatter(x=xl, y=tr(xl), mode="lines", name="추세선", line=dict(color="red", dash="dash")))
                    st.plotly_chart(fig, width="stretch")
                    st.write(f"상관계수: {dc['지상부 길이'].corr(dc['생중량']):.3f}")
                else:
                    st.info("지상부 길이와 생중량 데이터가 2개 미만입니다.")

            with st.expander("🌱 생육 데이터 원본 + CSV 다운로드"):
                st.dataframe(growth_merged, width="stretch")
                csv = growth_merged.to_csv(index=False).encode("utf-8-sig")
                st.download_button("생육 데이터 다운로드", csv, file_name="생육데이터.csv", mime="text/csv")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
