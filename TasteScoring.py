import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import itertools
import random
import time
import json

# --------------------------
# 1. CONFIG
# --------------------------
SCOPE = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1d_IqouXaflv0vl1xESD--T8eVHI5ACtD-ZklkDuZ9MQ"

# Use Streamlit secrets for credentials
creds_dict = st.secrets["google"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)

# --------------------------
# 2. PRODUCTS
# --------------------------
PRODUCTS = [
    "Tomatoes","Cucumbers","Bell peppers","Carrots","Onions","Potatoes","Garlic","Leeks","Celery",
    "Broccoli","Cauliflower","Lettuce","Spinach","Zucchini","Eggplant","Mushrooms","Sweet potatoes",
    "Fennel","Parsley root","Celeriac","Chili peppers","Green beans","Peas","Avocados","spinach",
    "Lettuce","Bananas","Apples","Pears","Oranges","Mandarins","Lemons","Limes","Grapefruits","Kiwis",
    "Mangoes","Papayas","Grapes","Melons","Pomegranates","Blueberries","Strawberries","Raspberries",
    "Blackberries","Peaches","Apricots","Dates","dried figs","dried apricots","dried grapes","Fruit mix",
    "Whole milk","Liquid cream","Plain yogurt","Raspberry yogurt","staberry yogurt","Greek yogurt",
    "Fromage blanc","Skyr","Kefir","Toasts","Emmental","Gruyère","Raclette cheese","Mozzarella","Feta",
    "Roquefort","Fromage frais","Fromage rapé","Cream cheese","Cottage cheese","Mascarpone","Ricotta",
    "Parmesan","Grana Padano","fondue cheese","eggs","Ketchup","Mayonnaise","Mustard","Bolognese",
    "Pesto","Paprika","Curry","Pesto rosso","Honey","Peanut Butter","dried tomatoes in oil",
    "Chicken breasts","Chicken thighs","Chicken wings","Minced chicken","Cordon bleu","Minced beef",
    "Beef steak","Roast beef","Filet of beef","Pork chops","Filet mignon","French Fries","Pork roast",
    "Minced pork","Bacon","Sausages","Veal","Smoked Salmon","Salmon steak","Cod","Perch fillets",
    "Tuna","Sardines","Shrimps","Mussels","Surimi","Pasta","Mixed rice","quinoa","couscous","Porridge"
]

# Remove duplicates
PRODUCTS = list(dict.fromkeys(PRODUCTS))

# Remove disliked products
REMOVED_PRODUCTS = ["Kefir", "Celery", "Raspberry yogurt", "Ricotta", "fondue cheese", "Skyr", "Surimi", "Pomegranates", "staberry yogurt", "Celeriac", "Chili peppers"]
PRODUCTS = [p for p in PRODUCTS if p not in REMOVED_PRODUCTS]

# --------------------------
# 3. CONNECT TO GOOGLE SHEET
# --------------------------
@st.cache_resource
def get_sheet_connection():
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

sheet = get_sheet_connection()

# --------------------------
# 4. LOAD EXISTING ANSWERS + AUTO-CLEAN SHEET
# --------------------------
def load_and_clean_existing_pairs():
    data = sheet.get_all_records()
    expected_headers = ["Product1", "Product2", "TasteScore"]

    # Create headers if missing
    if not data:
        headers = sheet.row_values(1)
        if headers != expected_headers:
            sheet.clear()
            sheet.append_row(expected_headers)
        return pd.DataFrame(columns=expected_headers)

    df = pd.DataFrame(data)

    # Remove any rows containing unwanted products
    before = len(df)
    df = df[~(df["Product1"].isin(REMOVED_PRODUCTS) | df["Product2"].isin(REMOVED_PRODUCTS))]
    after = len(df)

    # If rows were deleted → rewrite clean sheet
    if after < before:
             st.warning(f"🧹 Cleaning Google Sheet: removed {before - after} old ratings with unwanted products.")
             sheet.clear()
             sheet.append_row(expected_headers)
    
    # Batch append for efficiency and to avoid rate limits
             if not df.empty:
                 sheet.append_rows(df.values.tolist(), value_input_option="USER_ENTERED")


    return df

# --------------------------
# 5. COMPUTE REMAINING PAIRS
# --------------------------
def compute_remaining():
    existing_df = load_and_clean_existing_pairs()
    all_pairs = pd.DataFrame(list(itertools.combinations(PRODUCTS, 2)), columns=["Product1", "Product2"])
    remaining = all_pairs.merge(
        existing_df[["Product1", "Product2"]], on=["Product1", "Product2"], how="left", indicator=True
    )
    remaining = remaining[remaining["_merge"] == "left_only"].drop(columns="_merge")
    return all_pairs, existing_df, remaining

all_pairs, existing_df, remaining_pairs = compute_remaining()
total_pairs = len(all_pairs)
answered_pairs = total_pairs - len(remaining_pairs)
progress = answered_pairs / total_pairs

# --------------------------
# 6. STATE MANAGEMENT
# --------------------------
if "current_anchor" not in st.session_state:
    if remaining_pairs.empty:
        st.session_state.current_anchor = None
    else:
        st.session_state.current_anchor = remaining_pairs["Product1"].iloc[0]

# --------------------------
# 7. UI HEADER
# --------------------------
st.title("🥕 Taste Combination Game (Anchor Mode)")
st.markdown("""
You’ll rate **all combinations for one main product at a time**  
(e.g. *Peanut Butter + X*) — making grading faster and more consistent.
""")

st.progress(progress)
st.caption(f"Global progress: {answered_pairs:,}/{total_pairs:,} rated ({progress:.2%})")

# --------------------------
# 8. MAIN LOGIC
# --------------------------
if remaining_pairs.empty:
    st.success("🎉 You’ve rated every combination! Incredible work!")
else:
    current_anchor = st.session_state.current_anchor
    anchor_remaining = remaining_pairs[
        (remaining_pairs["Product1"] == current_anchor) | (remaining_pairs["Product2"] == current_anchor)
    ].reset_index(drop=True)

    # Switch to next anchor when current done
    if anchor_remaining.empty:
        next_anchor_candidates = [
            p for p in PRODUCTS if any((remaining_pairs["Product1"] == p) | (remaining_pairs["Product2"] == p))
        ]
        if next_anchor_candidates:
            st.session_state.current_anchor = next_anchor_candidates[0]
            st.rerun()
        else:
            st.success("🎉 All anchors done! You finished every combo.")
            st.stop()

    else:
        current_anchor = st.session_state.current_anchor
        st.header(f"🌟 Current product: **{current_anchor}**")

        total_for_anchor = len(PRODUCTS) - 1
        answered_for_anchor = total_for_anchor - len(anchor_remaining)
        st.caption(f"Progress for {current_anchor}: {answered_for_anchor}/{total_for_anchor}")

        # --- keep combo fixed until button pressed ---
        if "current_pair" not in st.session_state:
            st.session_state.current_pair = anchor_remaining.sample(1).iloc[0].to_dict()

        pair = st.session_state.current_pair
        p1, p2 = pair["Product1"], pair["Product2"]
        if p2 == current_anchor:
            p1, p2 = p2, p1

        st.subheader(f"🥇 **{p1} + {p2}**")
        score = st.slider("Select your taste score:", 1, 5, step=1, key="taste_slider")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save & Next ➡️"):
                sheet.append_row([p1, p2, score])
                st.success(f"Saved: {p1} + {p2} = {score}")
                st.session_state.pop("current_pair")
                time.sleep(0.4)
                st.rerun()

        with col2:
            if st.button("⏭️ Skip Combo"):
                st.session_state.pop("current_pair")
                time.sleep(0.3)
                st.rerun()

st.markdown("---")
st.caption("Your progress is always saved and cleaned automatically. You can close and come back anytime — it will resume exactly where you left off.")
