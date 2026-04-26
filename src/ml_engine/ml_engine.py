import pandas as pd
from sklearn.ensemble import IsolationForest
from src.config.config import PROCESS_LIMIT
from sklearn.preprocessing import StandardScaler
from src.logger.logger import Logger

logger = Logger().setup_logs()


def detect_anomalies(
    system_df: pd.DataFrame, contamination: float = 0.05
) -> pd.DataFrame:
    df = system_df.copy()
    df["anomaly"] = 0
    features = ["overall_cpu_load", "vm_percent_used"]
    valid = df[features].dropna()
    if len(valid) < 10:
        # not enough data
        return df
    try:
        scaler = StandardScaler()
        X = scaler.fit_transform(valid)
        clf = IsolationForest(contamination=contamination, random_state=42)
        preds = clf.fit_predict(X)
        df.loc[valid.index, "anomaly"] = (preds == -1).astype(int)
        n = df["anomaly"].sum()
        logger.info(f"Anomaly detection: {n}/{len(df)} anomalies flagged.")
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
    return df


def rank_anomalous_processes(
    process_df: pd.DataFrame, top_n: int = PROCESS_LIMIT
) -> pd.DataFrame:
    if process_df.empty:
        return pd.DataFrame()

    try:
        agg = (
            process_df.groupby("process_name")
            .agg(
                avg_cpu=("cpu_percent", "mean"),
                avg_mem=("memory_percent", "mean"),
                count=("cpu_percent", "count"),
            )
            .reset_index()
        )

        if len(agg) < 3:
            return agg

        mean_cpu = agg["avg_cpu"].mean()
        std_cpu = agg["avg_cpu"].std() or 1
        agg["cpu_zscore"] = ((agg["avg_cpu"] - mean_cpu) / std_cpu).round(2)
        agg["flagged"] = agg["cpu_zscore"] > 2.0

        return (
            agg.sort_values("avg_cpu", ascending=False)
            .head(top_n)
            .round(2)
            .reset_index(drop=True)
        )
    except Exception as e:
        logger.error(f"Process ranking error: {e}")
        return pd.DataFrame()


def detect_network_anomalies(network_df: pd.DataFrame) -> pd.DataFrame:
    df = network_df.copy()
    df["net_anomaly"] = False
    if df.empty or len(df) < 5:
        return df
    for col in ("upload_speed_mb", "download_speed_mb"):
        if col in df.columns:
            m, s = df[col].mean(), df[col].std() or 1
            df["net_anomaly"] |= df[col] > m + 2 * s
    return df


def compute_health_score(system_df: pd.DataFrame) -> dict:
    result = {
        "overall": 0,
        "cpu": 0,
        "memory": 0,
        "battery": 0,
        "anomaly_rate": 0,
        "grade": "N/A",
        "summary": "Not enough data.",
    }
    if system_df.empty or len(system_df) < 10:
        return result

    df = detect_anomalies(system_df)
    avg_cpu = system_df["overall_cpu_load"].mean()
    avg_mem = system_df["vm_percent_used"].mean()
    batt_col = system_df["battery_percent"].dropna()
    avg_batt = batt_col.mean() if not batt_col.empty else None
    anomaly_rate = df["anomaly"].mean() * 100

    cpu_score = max(0, 100 - avg_cpu)
    mem_score = max(0, 100 - avg_mem)
    batt_score = avg_batt if avg_batt else 70

    # taken this formula from llm
    overall = round(
        cpu_score * 0.4 + mem_score * 0.4 + batt_score * 0.2 - anomaly_rate * 0.5, 1
    )
    overall = max(0, min(100, overall))

    grade = (
        "A"
        if overall >= 85
        else (
            "B"
            if overall >= 70
            else "C" if overall >= 55 else "D" if overall >= 40 else "F"
        )
    )

    if grade in ("A", "B"):
        summary = f"System is running well. Avg CPU {avg_cpu:.1f}%, RAM {avg_mem:.1f}%."
    elif grade == "C":
        summary = f"Moderate load. Watch CPU ({avg_cpu:.1f}%) and RAM ({avg_mem:.1f}%)."
    else:
        summary = f"High load or many anomalies detected. CPU {avg_cpu:.1f}%, RAM {avg_mem:.1f}%, anomaly rate {anomaly_rate:.1f}%."

    result.update(
        {
            "overall": overall,
            "cpu": round(cpu_score, 1),
            "memory": round(mem_score, 1),
            "battery": round(batt_score, 1),
            "anomaly_rate": round(anomaly_rate, 1),
            "grade": grade,
            "summary": summary,
            "avg_cpu": round(avg_cpu, 1),
            "avg_mem": round(avg_mem, 1),
        }
    )
    return result
