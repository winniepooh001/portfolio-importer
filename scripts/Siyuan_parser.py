import json
import pandas as pd
from datetime import datetime
import sys
import io
from configs import SIYUAN_JSON

# Force stdout to use UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def parse_siyuan_trades(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = {}

    def get_row(block_id):
        if block_id not in rows:
            rows[block_id] = {}
        return rows[block_id]

    # 记录字段类型用于调试
    found_column_types = {}

    for kv in data.get("keyValues", []):
        col_name = kv["key"]["name"]
        col_type = kv["key"]["type"]
        found_column_types[col_name] = col_type

        for val in kv.get("values", []):
            block_id = val["blockID"]
            row = get_row(block_id)

            # ---- SELECT (Event Type) ----
            if col_type == "select":
                if val.get("mSelect"):
                    row[col_name] = val["mSelect"][0]["content"]

            # ---- NUMBER (Quantity, Price) ----
            elif col_type == "number":
                num = val.get("number")
                if num and num.get("isNotEmpty"):
                    row[col_name] = num["content"]

            # ---- DATE ----
            elif col_type == "date":
                date_obj = val.get("date")
                if date_obj and date_obj.get("isNotEmpty"):
                    ts = date_obj["content"] / 1000
                    row[col_name] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

            # ---- BLOCK / TEXT (ticker) ----
            elif col_type in ("block", "text"):
                block = val.get("block") or val.get("text")
                if block and block.get("content"):
                    row[col_name] = block["content"]

    df = pd.DataFrame.from_dict(rows, orient="index")

    # ---- 调试：查看所有抓取到的列名 ----
    print("\n--- DEBUG: 字段检测 ---")
    for c in df.columns:
        print(f"  - '{c}' (类型: {found_column_types.get(c)})")
    print("----------------------\n")

    # ---- 字段映射 ----
    # 请确保 "Price" 匹配你思源里的单价列名
    rename_map = {
        "Event Type": "Event Type",
        "Quantity": "Quantity",
        "ticker": "ticker",
        "日期": "Date",
        "exclude": "exclude",
        "price": "Price",  # <--- 如果你思源里叫“单价”，请改为 "单价": "price"
        "TradeThesis": "thesis",
        "CCY": "CCY",
        "FX_CAD": "FX_COST"
    }
    df = df.rename(columns=rename_map)
    cond = df['thesis'].str.match(r'^\d{10}')
    df.loc[~cond, 'thesis'] = ''
    # 确保必要列存在
    for col in ["ticker", "Quantity", "Price", "Date", "Event Type"]:
        if col not in df.columns:
            print(f"⚠️ 警告: 缺少列 '{col}'，将填充为空值")
            df[col] = pd.NA

    df["FX_COST"] = df["FX_COST"].fillna(1)
    # ---- 类型转换 ----
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)

    # ---- 手动计算 Book Cost (毛价) ----
    # 计算公式：数量 * 单价
    df["book_cost"] = df["Quantity"] * df["Price"] * df["FX_COST"]

    print(f"✅ 已手动计算 book_cost (共 {len(df)} 行)")

    # 排序
    df = df.sort_values("Date").reset_index(drop=True)

    return df


if __name__ == "__main__":

    OUTPUT_CSV = ""
    print(f"Will read json file from {SIYUAN_JSON} and load data into {OUTPUT_CSV}...")
    trades_df = parse_siyuan_trades(SIYUAN_JSON)

    # 打印前几行查看计算结果
    print("\n解析与计算结果预览:")
    print(trades_df.columns)
    print(trades_df[["date", "ticker", "quantity", "price", "book_cost"]].head())

    if OUTPUT_CSV:
        trades_df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n保存成功: {OUTPUT_CSV}")
    else:
        print("output path not provided file not saved")