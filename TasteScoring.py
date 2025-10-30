import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import itertools
import random

# --------------------------
# 1. CONFIG
# --------------------------
SCOPE = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

# Replace with your Google Sheet ID
SHEET_ID = "1d_IqouXaflv0vl1xESD--T8eVHI5ACtD-ZklkDuZ9MQ"
CREDENTIALS_FILE = "/Users/clementdurix/Library/CloudStorage/OneDrive-Personal/1. UNI/Uncertainty/TasteScoringCredentials.json"

# --------------------------
# 2. LOAD PRODUCTS
# --------------------------
PRODUCTS = [
    "Tomatoes","Cucumbers","Bell peppers","Carrots","Onions","Potatoes","Garlic","Leeks","Celery",
    "Broccoli","Cauliflower","Lettuce","Spinach","Zucchini","Eggplant","Mushrooms","Sweet potatoes",
    "Fennel","Parsley root","Celeriac","Chili peppers","Green beans","Peas","Avocados","spinach",
    "Lettuce","Bananas","Apples","Pears","Oranges","Mandarins","Lemons","Limes","Grapefruits","Kiwis",
    "Mangoes","Papayas","Grapes","Melons","Pomegranates","Blueberries","Strawberries","Raspberries",
    "Blackberries","Peaches","Apricots","Dates","dried figs","dried apricots","dried grapes","Fruit mix",
    "Whole milk","Liquid cream","Plain yogurt","staberry yogurt","Greek yogurt","Fromage blanc","Skyr",
    "Kefir","Toasts","Emmental","Gruyère","Raclette cheese","Mozzarella","Feta","Roquefort","Fromage frais",
    "Fromage rapé","Cream cheese","Cottage cheese","Mascarpone","Ricotta","Parmesan","Grana Padano",
    "fondue cheese","eggs","Ketchup","Mayonnaise","Mustard","Bolognese","Pesto","Paprika","Curry",
    "Pesto rosso","Honey","Peanut Butter","dried tomatoes in oil","Chicken breasts","Chicken thighs",
    "Chicken wings","Minced chicken","Cordon bleu","Minced beef","Beef steak","Roast beef","Filet of beef",
    "Pork chops","Filet mignon","French Fries","Pork roast","Minced pork","Bacon","Sausages","Veal",
    "Smoked Salmon","Salmon steak","Cod","Perch fillets","Tuna","Sardines","Shrimps","Mussels","Surimi",
    "Pasta","Mixed rice","quinoa","couscous","Porridge"
]

PRODUCTS = list(dict.fromkeys(PRODUCTS))  # remove duplicates (e.g., Spinach appears twice)

# --------------------------
# 3. CONNECT TO GOOGLE SHEET
# --------------------------
@st.cache_resource
def get_sheet_connection():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    return sheet

sheet = get_sheet_connection()

# --------------------------
# 4. LOAD EXISTING ANSWERS
# --------------------------
def load_existing_pairs():
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Product1", "Product2", "TasteScore"])
    return pd.DataFrame(data)

existing_df = load_existing_pairs()

# --------------------------
# 5. GENERATE REMAINING PAIRS
# --------------------------
all_pairs = pd.DataFrame(list(itertools.combinations(PRODUCTS, 2)), columns=["Product1", "Product2"])

# Remove already rated pairs
remaining_pairs = all_pairs.merge(existing_df[["Product1","Product2"]], on=["Product1","Product2"], how="left", indicator=True)
remaining_pairs = remaining_pairs[remaining_pairs["_merge"] == "left_only"].drop(columns="_merge")

# Shuffle for randomness
remaining_pairs = remaining_pairs.sample(frac=1, random_state=None).reset_index(drop=True)

# --------------------------
# 6. MAIN UI
# --------------------------
st.title("🥕 Taste Combination Game")
st.markdown("Rate how tasty each combination feels from **1 (disgusting)** to **5 (excellent)**.")

if remaining_pairs.empty:
    st.success("🎉 You’ve rated all possible pairs! Thank you!")
else:
    pair = remaining_pairs.iloc[0]
    st.subheader(f"How does this combo sound?")
    st.markdown(f"### 🥇 **{pair['Product1']} + {pair['Product2']}**")

    score = st.slider("Select your taste score:", 1, 5, step=1)

    if st.button("Save & Next ➡️"):
        sheet.append_row([pair["Product1"], pair["Product2"], score])
        st.success(f"Saved {pair['Product1']} + {pair['Product2']} = {score}")
        st.rerun()

st.markdown("---")
st.caption("Progress is saved automatically to your Google Sheet. You can close and return anytime.")
