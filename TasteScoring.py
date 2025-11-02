import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import itertools
import time

# --------------------------
# 1) CONFIG
# --------------------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
SHEET_ID = "1d_IqouXaflv0vl1xESD--T8eVHI5ACtD-ZklkDuZ9MQ"

# Credentials come from Streamlit Secrets (Settings → Secrets)
creds_dict = st.secrets["google"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)

# --------------------------
# 2) PRODUCTS (universe)
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
# de-duplicate (e.g., Lettuce/Spinach appear twice)
PRODUCTS = list(dict.fromkeys(PRODUCTS))

# Products you never want to rate again (filtered IN-MEMORY ONLY; no deletions)
REMOVED_PRODUCTS = [
    "Kefir", "Celery", "Raspberry yogurt", "Ricotta", "fondue cheese", "Skyr",
    "Surimi", "Pomegranates", "staberry yogurt", "Celeriac", "Chili peppers", "Melons", "Fennel", "spinach", "Parsley root", "Mascarpone", "Limes"
]
PRODUCTS = [p for p in PRODUCTS if p not in REMOVED_PRODUCTS]

# --------------------------
# 3) GOOGLE SHEET CONNECTION
# --------------------------
@st.cache_resource
def get_sheet():
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

sheet = get_sheet()

# --------------------------
# 4) READ EXISTING ANSWERS (NON-DESTRUCTIVE)
# --------------------------
def load_existing_pairs_readonly() -> pd.DataFrame:
    """
    Reads the whole sheet safely without editing it.
    - If empty, creates the header row once.
    - If headers differ, tries best-effort mapping in-memory.
    - Filters out rows that contain removed products (for progress & remaining calcs),
      WITHOUT deleting anything from the sheet.
    """
    expected = ["Product1", "Product2", "TasteScore"]
    rows = sheet.get_all_values()

    # If truly empty: create headers once and return empty df
    if not rows:
        sheet.append_row(expected)
        return pd.DataFrame(columns=expected)

    headers = rows[0]
    data = rows[1:]

    if headers != expected:
        # map by name if present; otherwise return empty df
        try:
            i1 = headers.index("Product1")
            i2 = headers.index("Product2")
            i3 = headers.index("TasteScore") if "TasteScore" in headers else None
        except ValueError:
            return pd.DataFrame(columns=expected)

        recs = []
        for r in data:
            # guard for short rows
            max_idx = max([i1, i2] + ([i3] if i3 is not None else [0]))
            if len(r) <= max_idx:
                continue
            recs.append({
                "Product1": r[i1],
                "Product2": r[i2],
                "TasteScore": r[i3] if i3 is not None else ""
            })
        df = pd.DataFrame(recs, columns=expected)
    else:
        df = pd.DataFrame(data, columns=expected)

    # Ignore any rows that include removed products (no deletion)
    mask_ok = ~(
        df["Product1"].isin(REMOVED_PRODUCTS) | df["Product2"].isin(REMOVED_PRODUCTS)
    )
    return df[mask_ok].reset_index(drop=True)

# --------------------------
# 5) BUILD REMAINING PAIRS (READ-ONLY)
# --------------------------
def compute_remaining():
    existing_df = load_existing_pairs_readonly()

    # All unordered pairs from the (filtered) product universe
    all_pairs = pd.DataFrame(
        list(itertools.combinations(PRODUCTS, 2)),
        columns=["Product1", "Product2"]
    )

    # Remove already rated pairs
    remaining = all_pairs.merge(
        existing_df[["Product1", "Product2"]],
        on=["Product1", "Product2"],
        how="left",
        indicator=True
    )
    remaining = remaining[remaining["_merge"] == "left_only"].drop(columns="_merge")
    return all_pairs, existing_df, remaining

# ----- compute datasets & progress BEFORE any UI that uses them -----
all_pairs, existing_df, remaining_pairs = compute_remaining()
total_pairs = len(all_pairs)
answered_pairs = total_pairs - len(remaining_pairs)
progress = 0.0 if total_pairs == 0 else answered_pairs / total_pairs

# --------------------------
# 6) STATE (anchor + fixed combo)
# --------------------------
if "current_anchor" not in st.session_state:
    if remaining_pairs.empty:
        st.session_state.current_anchor = None
    else:
        # Choose first available product that still has any remaining pair
        first_pair = remaining_pairs.iloc[0]
        st.session_state.current_anchor = first_pair["Product1"]

# --------------------------
# 7) UI HEADER
# --------------------------
st.title("🥕 Taste Combination Game (Anchor Mode)")
st.markdown(
    "Rate **all combinations for one main product at a time** "
    "(e.g., *Peanut Butter + X*) — faster and more consistent."
)
st.progress(progress)
st.caption(f"Global progress: {answered_pairs:,}/{total_pairs:,} rated ({progress:.2%})")

# --------------------------
# 8) MAIN LOGIC
# --------------------------
if remaining_pairs.empty:
    st.success("🎉 You’ve rated every combination in the current universe! Amazing!")
else:
    current_anchor = st.session_state.current_anchor
    # Remaining pairs for this anchor (anchor may be first or second in the pair)
    anchor_remaining = remaining_pairs[
        (remaining_pairs["Product1"] == current_anchor) |
        (remaining_pairs["Product2"] == current_anchor)
    ].reset_index(drop=True)

    # If this anchor is done, jump to the next anchor that still has pairs
    if anchor_remaining.empty:
        next_anchor_candidates = [
            p for p in PRODUCTS
            if any((remaining_pairs["Product1"] == p) | (remaining_pairs["Product2"] == p))
        ]
        if next_anchor_candidates:
            st.session_state.current_anchor = next_anchor_candidates[0]
            st.rerun()
        else:
            st.success("🎉 All anchors done! You finished every combo.")
            st.stop()
    else:
        st.header(f"🌟 Current product: **{current_anchor}**")
        total_for_anchor = len(PRODUCTS) - 1  # pairs current anchor can have
        answered_for_anchor = total_for_anchor - len(anchor_remaining)
        st.caption(f"Progress for {current_anchor}: {answered_for_anchor}/{total_for_anchor}")

        # Keep the same combo visible while moving the slider
        if "current_pair" not in st.session_state:
            st.session_state.current_pair = anchor_remaining.sample(1).iloc[0].to_dict()

        pair = st.session_state.current_pair
        p1, p2 = pair["Product1"], pair["Product2"]
        # ensure anchor is printed first
        if p2 == current_anchor:
            p1, p2 = p2, p1

        st.subheader(f"🥇 **{p1} + {p2}**")
        score = st.slider("Select your taste score:", 1, 5, step=1, key="taste_slider")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save & Next ➡️"):
                # Append one new rating row (this is the ONLY write)
                sheet.append_row([p1, p2, score])
                st.success(f"Saved: {p1} + {p2} = {score}")
                # Reset current pair so a new one is picked after rerun
                st.session_state.pop("current_pair", None)
                time.sleep(0.3)
                st.rerun()

        with col2:
            if st.button("⏭️ Skip Combo"):
                # No write; just pick a different pair on rerun
                st.session_state.pop("current_pair", None)
                time.sleep(0.2)
                st.rerun()

st.markdown("---")
st.caption("Your past ratings are preserved. Removed products are filtered in-memory only, "
           "so totals and progress adjust without deleting any of your data.")
