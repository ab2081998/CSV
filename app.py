import io
import os
import zipfile

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Warmup CSV Splitter", layout="centered")
st.title("Email Warmup CSV Splitter")

# 1. File Upload UI
uploaded_file = st.file_uploader("Apni Master CSV file upload karein", type=["csv"])
no_header_csv = st.checkbox(
    "Uploaded CSV mein koi header row nahi hai (pehli row hi email address hai)",
    value=False,
)

# 2. Schedule Mode Selection
st.subheader("Email Volume Schedule")
mode = st.radio(
    "Schedule Mode chunein:",
    ["Auto Multiplier (Base × Increase per Day)", "Manual Day-by-Day Boxes (15 Days)"],
    horizontal=True,
)

daily_volumes = []

if mode == "Auto Multiplier (Base × Increase per Day)":
    col1, col2, col3 = st.columns(3)
    with col1:
        base_emails = st.number_input("Base Emails (Day 1)", min_value=1, value=200, step=50)
    with col2:
        multiplier = st.number_input(
            "Daily Increase Multiplier", min_value=1.0, value=1.5, step=0.1, format="%.2f"
        )
    with col3:
        num_days = st.number_input("No. of Days Needed", min_value=1, max_value=60, value=15, step=1)

    # Calculate daily volumes: Day 1 = base, Day 2 = base * multiplier ...
    current_vol = float(base_emails)
    for day in range(1, int(num_days) + 1):
        vol = round(current_vol)
        daily_volumes.append((day, vol))
        current_vol *= multiplier

    # Show generated schedule preview
    with st.expander("Generated Day-by-Day Schedule Dekhein", expanded=True):
        preview_df = pd.DataFrame(daily_volumes, columns=["Day", "Emails Needed"])
        preview_df["Day"] = preview_df["Day"].apply(lambda d: f"Day {d}")
        st.dataframe(preview_df.T, use_container_width=True)
else:
    default_volumes = [
        200, 400, 900, 1400, 2300,
        3500, 5000, 7000, 9500, 12000,
        15000, 20000, 25000, 30000, 35000,
    ]
    st.caption("Har din ke liye kitne emails chahiye wo niche boxes mein enter karein:")
    for row in range(3):
        cols = st.columns(5)
        for col_idx in range(5):
            day_num = row * 5 + col_idx + 1
            with cols[col_idx]:
                vol = st.number_input(
                    f"Day {day_num}",
                    min_value=0,
                    value=default_volumes[day_num - 1],
                    step=100,
                    key=f"day_{day_num}",
                )
                daily_volumes.append((day_num, vol))

# 3. Process Uploaded CSV
if uploaded_file is not None:
    base_name = os.path.splitext(uploaded_file.name)[0]
    read_kwargs = {"header": None} if no_header_csv else {}
    df = pd.read_csv(uploaded_file, **read_kwargs)

    # Normalize column names to ensure "email" is used consistently
    df.columns = [str(col).strip().lower() for col in df.columns]
    email_aliases = {"email", "e-mail", "e_mail", "email_address", "email address", "mail"}
    for col in df.columns:
        if col in email_aliases:
            df.rename(columns={col: "email"}, inplace=True)
            break
    if "email" not in df.columns and len(df.columns) == 1:
        df.columns = ["email"]

    if "email" not in df.columns:
        st.error("Uploaded CSV mein 'email' column nahi mila.")
    else:
        df = df[["email"]].dropna()
        df["email"] = df["email"].astype(str).str.strip()
        df = df[df["email"] != ""].reset_index(drop=True)

        total_rows = len(df)
        required_sum = sum(vol for _, vol in daily_volumes)
        remaining_est = max(0, total_rows - required_sum)

        st.info(
            f"**Uploaded File:** `{uploaded_file.name}` | "
            f"**Total Rows:** `{total_rows:,}` | "
            f"**Total Needed ({len(daily_volumes)} Days):** `{required_sum:,}` | "
            f"**Estimated Remaining:** `{remaining_est:,}`"
        )

        if required_sum > total_rows:
            st.warning(
                f"⚠️ Total required emails ({required_sum:,}) file ki total rows ({total_rows:,}) se zyada hain. "
                "Jahan rows khatam hongi, split wahin ruk jayega."
            )

        randomize = st.checkbox("Upload ke baad rows ko Randomize (Shuffle) karein", value=True)

        if st.button("Split CSV Files", type="primary"):
            if randomize:
                df = df.sample(frac=1, random_state=None).reset_index(drop=True)

            zip_buffer = io.BytesIO()
            start_idx = 0
            summary_data = []

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for day, volume in daily_volumes:
                    if volume <= 0:
                        continue
                    if start_idx >= total_rows:
                        break
                    end_idx = start_idx + volume
                    chunk = df.iloc[start_idx:end_idx]
                    out_filename = f"{base_name}_Day{day}.csv"
                    csv_bytes = chunk.to_csv(
                        columns=["email"], header=["email"], index=False
                    ).encode("utf-8")
                    zip_file.writestr(out_filename, csv_bytes)
                    summary_data.append(
                        {"Day": f"Day {day}", "File Name": out_filename, "Email Count": len(chunk)}
                    )
                    start_idx = end_idx

                # Remaining emails after all scheduled days
                if start_idx < total_rows:
                    remaining = df.iloc[start_idx:]
                    rem_filename = f"{base_name}_Remaining.csv"
                    rem_bytes = remaining.to_csv(
                        columns=["email"], header=["email"], index=False
                    ).encode("utf-8")
                    zip_file.writestr(rem_filename, rem_bytes)
                    summary_data.append(
                        {"Day": "Remaining", "File Name": rem_filename, "Email Count": len(remaining)}
                    )

            if summary_data:
                st.success(f"Total {len(summary_data)} files taiyar hain!")
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
                st.download_button(
                    label="Download All Split CSVs (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"{base_name}_split_files.zip",
                    mime="application/zip",
                )
            else:
                st.error("Koi file generate nahi hui. Kripya valid email count dalein.")
