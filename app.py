import streamlit as st
import sqlite3
import pandas as pd
from database import init_db
# -------------------------------------------------------------------
# DB Connection & Helper Functions
# -------------------------------------------------------------------
DB_PATH = "leads.db"
init_db()
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_leads():
    conn = get_db_connection()
    # Assuming standard tables or normalized tables in leads.db
    query = """
    SELECT 
        id, client_name, phone_number, intent, lead_tag, 
        preferred_location, property_type, budget_range,
        ownership_type, land_area, mouza_location, doc_type, asking_price,
        created_at
    FROM leads
    ORDER BY created_at DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
    except Exception:
        # Fallback query if flat leads table is used
        query = "SELECT * FROM leads ORDER BY rowid DESC"
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return df

def get_db_connection():
    return sqlite3.connect(DB_PATH)

# Add navigation tabs to your dashboard
tab1, tab2 = st.tabs(["📋 Lead Tracking", "🏠 Inventory & Listings"])

with tab1:
    st.subheader("Captured Leads")
    # ... (Your existing lead management code)

with tab2:
    st.subheader("➕ Add New Inventory / Property")
    
    with st.form("add_property_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            title = st.text_input("Listing Title", placeholder="e.g. 10 Marla Plot near Main Bazar")
            property_type = st.selectbox("Property Type", ["Plot", "Residential House", "Commercial", "Agricultural Land"])
            intent_type = st.selectbox("Listing Purpose", ["FOR_SALE", "WANTED"])
            location_mouza = st.text_input("Mouza / Location", placeholder="e.g. Mouza Wandhi, Mianwali")
            land_area = st.text_input("Land Area", placeholder="e.g. 10 Marla / 2 Kanal")
            
        with col2:
            asking_price = st.number_input("Demand / Price (PKR)", min_value=0.0, step=50000.0)
            ownership_type = st.selectbox("Ownership Type", ["fard_e_wahid", "khata_shareek", "Unknown"])
            doc_type = st.selectbox("Document Type", ["Registry", "Inteqal", "Stamp", "Unknown"])
            description = st.text_area("Key Details / Highlights", placeholder="Mention features, road width, urgency, etc.")
            
        submitted = st.form_submit_button("🚀 Publish Property")
        
        if submitted:
            if title and location_mouza:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO properties 
                    (title, property_type, intent_type, location_mouza, land_area, asking_price, ownership_type, doc_type, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (title, property_type, intent_type, location_mouza, land_area, asking_price, ownership_type, doc_type, description))
                conn.commit()
                conn.close()
                st.success(f"Property '{title}' added to active inventory!")
            else:
                st.error("Please fill in the required fields (Title & Location).")

    st.divider()
    st.subheader("📦 Current Active Inventory")
    
    conn = get_db_connection()
    properties_df = pd.read_sql_query("SELECT * FROM properties WHERE status='AVAILABLE' ORDER BY created_at DESC", conn)
    conn.close()
    
    st.dataframe(properties_df, use_container_width=True)

# -------------------------------------------------------------------
# Page Config & Header
# -------------------------------------------------------------------
st.set_page_config(page_title="Malik Property - Lead Intelligence Dashboard", layout="wide")
st.title("🏡 Malik Property — Lead Intelligence Dashboard")
st.caption("Real-time automated WhatsApp lead tracking and CRM insights")

# Refresh Button
if st.button("🔄 Refresh Data"):
    st.rerun()

# -------------------------------------------------------------------
# Data Loading & Overview Metrics
# -------------------------------------------------------------------
df = load_leads()

if df.empty:
    st.warning("No lead data found in leads.db yet.")
    st.stop()

# Key Performance Indicators (KPIs)
col1, col2, col3, col4 = st.columns(4)

total_leads = len(df)
hot_leads = len(df[df['lead_tag'] == 'HOT']) if 'lead_tag' in df.columns else 0
buyer_leads = len(df[df['intent'] == 'BUY']) if 'intent' in df.columns else 0
seller_leads = len(df[df['intent'] == 'SELL']) if 'intent' in df.columns else 0

col1.metric("Total Captured Leads", total_leads)
col2.metric("🔥 Hot Leads", hot_leads)
col3.metric("🏠 Buyers", buyer_leads)
col4.metric("🏷️ Sellers", seller_leads)

st.divider()

# -------------------------------------------------------------------
# Filters Section
# -------------------------------------------------------------------
st.sidebar.header("Filter Leads")

intent_filter = st.sidebar.multiselect(
    "Filter by Intent",
    options=df['intent'].unique() if 'intent' in df.columns else [],
    default=df['intent'].unique() if 'intent' in df.columns else []
)

tag_filter = st.sidebar.multiselect(
    "Filter by Lead Tag",
    options=df['lead_tag'].unique() if 'lead_tag' in df.columns else [],
    default=df['lead_tag'].unique() if 'lead_tag' in df.columns else []
)

filtered_df = df.copy()

if intent_filter and 'intent' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['intent'].isin(intent_filter)]

if tag_filter and 'lead_tag' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['lead_tag'].isin(tag_filter)]

# -------------------------------------------------------------------
# Detailed Data View & Editing
# -------------------------------------------------------------------
st.subheader("📋 Lead Table")

# Format dataframe tags visually
st.dataframe(
    filtered_df,
    use_container_width=True,
    column_config={
        "lead_tag": st.column_config.SelectboxColumn(
            "Lead Status",
            options=["HOT", "WARM", "COLD"],
            required=True
        ),
        "intent": st.column_config.SelectboxColumn(
            "Intent",
            options=["BUY", "SELL", "INQUIRY"],
            required=True
        )
    }
)

# Export Functionality
st.download_button(
    label="📥 Export Leads to CSV",
    data=filtered_df.to_csv(index=False).encode('utf-8'),
    file_name='malik_property_leads.csv',
    mime='text/csv'
)