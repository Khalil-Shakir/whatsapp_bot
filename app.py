import streamlit as st
import sqlite3
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import init_db

# -------------------------------------------------------------------
# Page Config (MUST be the first Streamlit command)
# -------------------------------------------------------------------
st.set_page_config(page_title="Malik Property - Lead Intelligence Dashboard", layout="wide")

DB_PATH = "leads.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
init_db()

# -------------------------------------------------------------------
# DB Connection & Helper Functions
# -------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_full_leads():
    """Performs LEFT JOINs across relational tables to merge lead, buyer, and seller data."""
    conn = get_db_connection()
    query = """
    SELECT 
        l.id AS lead_id,
        l.client_name,
        l.phone_number,
        l.intent,
        l.lead_tag,
        -- Buyer Preferences
        b.preferred_location,
        b.property_type AS buyer_property_type,
        b.budget_range,
        -- Seller Properties
        s.ownership_type,
        s.land_are AS seller_land_area,
        s.mouza_location,
        s.doc_type,
        s.asking_price AS seller_asking_price,
        l.created_at,
        l.updated_at
    FROM leads l
    LEFT JOIN buyer_preferences b ON l.id = b.lead_id
    LEFT JOIN seller_properties s ON l.id = s.lead_id
    ORDER BY l.updated_at DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error reading lead data: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def load_conversation_logs():
    """Fetches full chat history with lead details."""
    conn = get_db_connection()
    query = """
    SELECT 
        c.id AS log_id,
        l.id AS lead_id,
        l.phone_number,
        COALESCE(l.client_name, 'Unknown') AS client_name,
        c.sender,
        c.message_text,
        c.timestamp
    FROM conversation_logs c
    JOIN leads l ON c.lead_id = l.id
    ORDER BY c.timestamp DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

# -------------------------------------------------------------------
# Header & Refresh Button
# -------------------------------------------------------------------
st.title("🏡 Malik Property — Lead Intelligence Dashboard")
st.caption("Real-time automated WhatsApp lead tracking and CRM insights")

col_head1, col_head2 = st.columns([6, 1])
with col_head2:
    if st.button("🔄 Refresh Data"):
        st.rerun()

# -------------------------------------------------------------------
# Navigation Tabs
# -------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Combined Lead Intelligence", 
    "📊 Visual Analytics & Insights", 
    "🏠 Inventory & Listings", 
    "💬 Conversation Logs"
])

# ================= ================= ================= =============
# TAB 1: COMBINED LEADS
# ================= ================= ================= =============
with tab1:
    df = load_full_leads()

    if df.empty:
        st.warning("No lead data found in leads.db yet.")
    else:
        # Key Performance Indicators (KPIs)
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        total_leads = len(df)
        hot_leads = len(df[df['lead_tag'] == 'HOT']) if 'lead_tag' in df.columns else 0
        buyer_leads = len(df[df['intent'] == 'BUY']) if 'intent' in df.columns else 0
        seller_leads = len(df[df['intent'] == 'SELL']) if 'intent' in df.columns else 0

        kpi1.metric("Total Captured Leads", total_leads)
        kpi2.metric("🔥 Hot Leads", hot_leads)
        kpi3.metric("🏠 Buyers", buyer_leads)
        kpi4.metric("🏷️ Sellers", seller_leads)

        st.divider()

        # Sidebar Filters
        st.sidebar.header("Filter Leads")
        intent_filter = st.sidebar.multiselect(
            "Filter by Intent",
            options=df['intent'].dropna().unique() if 'intent' in df.columns else [],
            default=df['intent'].dropna().unique() if 'intent' in df.columns else []
        )

        tag_filter = st.sidebar.multiselect(
            "Filter by Lead Tag",
            options=df['lead_tag'].dropna().unique() if 'lead_tag' in df.columns else [],
            default=df['lead_tag'].dropna().unique() if 'lead_tag' in df.columns else []
        )

        filtered_df = df.copy()
        if intent_filter and 'intent' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['intent'].isin(intent_filter)]
        if tag_filter and 'lead_tag' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['lead_tag'].isin(tag_filter)]

        st.subheader("📋 Unified Lead Table (Leads + Buyers + Sellers)")
        st.dataframe(
            filtered_df,
            use_container_width=True,
            column_config={
                "lead_tag": st.column_config.SelectboxColumn("Lead Status", options=["HOT", "WARM", "COLD"]),
                "intent": st.column_config.SelectboxColumn("Intent", options=["BUY", "SELL", "INQUERY"])
            }
        )

        st.download_button(
            label="📥 Export Unified Leads to CSV",
            data=filtered_df.to_csv(index=False).encode('utf-8'),
            file_name='malik_property_unified_leads.csv',
            mime='text/csv'
        )

# ================= ================= ================= =============
# TAB 2: VISUAL ANALYTICS & INSIGHTS
# ================= ================= ================= =============
with tab2:
    st.subheader("📈 Real Estate Intelligence & Performance Visuals")
    df_analytics = load_full_leads()

    if df_analytics.empty:
        st.info("Insufficient data available to generate visual analytics.")
    else:
        col_chart1, col_chart2 = st.columns(2)

        # 1. Lead Conversion Funnel
        with col_chart1:
            st.markdown("**🎯 Lead Conversion Funnel**")
            # Calculate funnel counts dynamically
            tag_counts = df_analytics['lead_tag'].value_counts() if 'lead_tag' in df_analytics.columns else pd.Series()
            
            funnel_stages = ["New Lead", "Hot Lead", "Site Visit Scheduled", "Closed Deal"]
            funnel_values = [
                len(df_analytics),
                tag_counts.get("HOT", 0),
                tag_counts.get("WARM", 0),  # Mapped WARM as operational proxy
                tag_counts.get("CLOSED", 0)
            ]

            fig_funnel = go.Figure(go.Funnel(
                y=funnel_stages,
                x=funnel_values,
                textinfo="value+percent initial",
                marker={"color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]}
            ))
            fig_funnel.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=350)
            st.plotly_chart(fig_funnel, use_container_width=True)

        # 2. Demand Heatmap / Bar Chart by Mouza
        with col_chart2:
            st.markdown("**📍 Location / Mouza Demand Hotspots**")
            # Combine preferred location from buyers and seller mouzas
            mouza_series = df_analytics['preferred_location'].fillna(df_analytics['mouza_location']).dropna()
            
            if not mouza_series.empty:
                mouza_counts = mouza_series.value_counts().reset_index()
                mouza_counts.columns = ['Mouza / Location', 'Demand Count']
                
                fig_mouza = px.bar(
                    mouza_counts.head(8), 
                    x='Demand Count', 
                    y='Mouza / Location', 
                    orientation='h',
                    color='Demand Count',
                    color_continuous_scale='Viridis',
                    text='Demand Count'
                )
                fig_mouza.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=20, r=20, t=20, b=20), height=350)
                st.plotly_chart(fig_mouza, use_container_width=True)
            else:
                st.info("No location/mouza data available yet.")

        st.divider()
        col_chart3, col_chart4 = st.columns(2)

        # 3. Budget vs. Asking Price Scatter Plot
        with col_chart3:
            st.markdown("**💰 Buyer Budget vs. Seller Asking Price**")
            
            # Clean numerical fields
            df_analytics['budget_num'] = pd.to_numeric(df_analytics['budget_range'], errors='coerce')
            df_analytics['asking_num'] = pd.to_numeric(df_analytics['seller_asking_price'], errors='coerce')

            plot_df = df_analytics.dropna(subset=['budget_num', 'asking_num'], how='all')

            if not plot_df.empty:
                fig_scatter = px.scatter(
                    plot_df,
                    x='budget_num',
                    y='asking_num',
                    color='intent',
                    hover_data=['client_name', 'phone_number'],
                    labels={'budget_num': 'Buyer Budget (PKR)', 'asking_num': 'Seller Asking Price (PKR)'},
                    title="Price Alignment Scatter"
                )
                fig_scatter.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=350)
                st.plotly_chart(fig_scatter, use_container_width=True)
            else:
                st.info("Numeric budget and asking price data needed for scatter plot.")

        # 4. Lead Inflow Trends
        with col_chart4:
            st.markdown("**📅 Daily Lead Inflow Trend**")
            if 'created_at' in df_analytics.columns:
                df_analytics['created_date'] = pd.to_datetime(df_analytics['created_at'], errors='coerce').dt.date
                trend_df = df_analytics.groupby('created_date').size().reset_index(name='Lead Count')
                
                fig_trend = px.line(
                    trend_df, 
                    x='created_date', 
                    y='Lead Count', 
                    markers=True,
                    labels={'created_date': 'Date', 'Lead Count': 'Captured Leads'}
                )
                fig_trend.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=350)
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("Creation timestamp data unavailable for trend chart.")

# ================= ================= ================= =============
# TAB 3: INVENTORY & LISTINGS
# ================= ================= ================= =============
with tab3:
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

        uploaded_image = st.file_uploader("📸 Upload Property Photo (JPEG/PNG)", type=["jpg", "jpeg", "png"])
        submitted = st.form_submit_button("🚀 Publish Property")
        
        if submitted:
            if title and location_mouza:
                saved_image_path = None
                if uploaded_image is not None:
                    file_extension = os.path.splitext(uploaded_image.name)[1]
                    filename = f"prop_{int(pd.Timestamp.now().timestamp())}{file_extension}"
                    saved_image_path = os.path.join(UPLOAD_DIR, filename)
                    
                    with open(saved_image_path, "wb") as f:
                        f.write(uploaded_image.getbuffer())
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO properties 
                    (title, property_type, intent_type, location_mouza, land_area, asking_price, ownership_type, doc_type, description, image_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (title, property_type, intent_type, location_mouza, land_area, asking_price, ownership_type, doc_type, description, saved_image_path))
                conn.commit()
                conn.close()
                st.success(f"Property '{title}' added to active inventory!")
                st.rerun()
            else:
                st.error("Please fill in required fields (Title & Location).")

    st.divider()
    st.subheader("📦 Current Active Inventory")
    
    conn = get_db_connection()
    properties_df = pd.read_sql_query("SELECT * FROM properties WHERE status='AVAILABLE' ORDER BY created_at DESC", conn)
    conn.close()
    
    st.dataframe(properties_df, use_container_width=True)

# ================= ================= ================= =============
# TAB 4: CONVERSATION LOGS
# ================= ================= ================= =============
with tab4:
    st.subheader("💬 WhatsApp Chat History Logs")
    logs_df = load_conversation_logs()
    
    if logs_df.empty:
        st.info("No conversation logs recorded yet.")
    else:
        st.dataframe(
            logs_df,
            use_container_width=True,
            column_config={
                "sender": st.column_config.SelectboxColumn("Sender", options=["CLIENT", "BOT"])
            }
        )