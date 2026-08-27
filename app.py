import streamlit as st
import sqlite3
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
import re
from database import (init_db, get_buyer_matches, get_leads_due_today, update_lead_pipeline, delete_sold_property)
import io
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# -------------------------------------------------------------------
# Page Config (MUST be the first Streamlit command)
# -------------------------------------------------------------------
st.set_page_config(page_title="Malik Property - Lead Intelligence Dashboard", layout="wide")
due_leads = get_leads_due_today()

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

# --- WHATSAPP UTILITY FUNCTIONS ---
def format_pk_phone(phone_str: str) -> str:
    """Sanitizes phone numbers to Pakistani format: 923XXXXXXXXX."""
    digits = re.sub(r'\D', '', str(phone_str))
    if digits.startswith("03") and len(digits) == 11:
        return "92" + digits[1:]
    elif digits.startswith("923") and len(digits) == 12:
        return digits
    elif digits.startswith("3") and len(digits) == 10:
        return "92" + digits
    return digits

def generate_wa_link(phone: str, text: str = "") -> str:
    """Generates an auto-formatted wa.me URL with optional pre-filled text."""
    clean_phone = format_pk_phone(phone)
    if not text:
        return f"https://wa.me/{clean_phone}"
    encoded_text = urllib.parse.quote(text)
    return f"https://wa.me/{clean_phone}?text={encoded_text}"

def generate_leads_pdf(df):
    """Generates a PDF bytes object from the leads DataFrame."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=22, textColor=colors.HexColor('#1E3A8A'))
    story.append(Paragraph("<b>Malik Property — Unified Leads Summary</b>", title_style))
    story.append(Spacer(1, 10))

    cols_to_include = ['lead_id', 'client_name', 'phone_number', 'intent', 'lead_tag', 'buyer_location', 'buyer_budget']
    available_cols = [col for col in cols_to_include if col in df.columns]
    
    pdf_df = df[available_cols].fillna('N/A')
    headers = [col.replace('_', ' ').title() for col in available_cols]
    
    cell_style = ParagraphStyle('CellStyle', fontSize=8, leading=10)
    header_style = ParagraphStyle('HeaderStyle', fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.white)

    data = [[Paragraph(h, header_style) for h in headers]]
    
    for _, row in pdf_df.iterrows():
        row_data = [Paragraph(str(val), cell_style) for val in row.values]
        data.append(row_data)

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))

    story.append(table)
    doc.build(story)
    
    buffer.seek(0)
    return buffer.getvalue()

def load_full_leads():
    """Performs LEFT JOINs across relational tables to merge lead, buyer, and seller data."""
    conn = get_db_connection()
    query = """
    SELECT 
        l.id AS lead_id,
        COALESCE(NULLIF(l.client_name, ''), 'Awaiting Name') AS client_name,
        l.phone_number,
        l.intent,
        l.lead_tag,
        -- Buyer Preferences
        b.preferred_location AS buyer_location,
        b.property_type AS buyer_property_type,
        b.land_area AS buyer_land_area,
        b.budget_range AS buyer_budget,
        -- Seller Properties
        s.mouza_location AS seller_mouza,
        s.land_area AS seller_land_area,    
        s.ownership_type AS seller_ownership,
        s.doc_type AS seller_doc_type,
        COALESCE(NULLIF(s.asking_price, ''), 'Dealer Market Estimate Required') AS seller_asking_price,
        l.created_at,
        l.updated_at
    FROM leads l
    LEFT JOIN buyer_profiles b ON l.id = b.lead_id
    LEFT JOIN seller_profiles s ON l.id = s.lead_id
    ORDER BY l.updated_at DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
        # Dynamic WhatsApp link generation for each record
        if not df.empty and 'phone_number' in df.columns:
            df['wa_link'] = df['phone_number'].apply(lambda p: generate_wa_link(p))
    except Exception as e:
        # Fallback if your DB tables use the older _preferences naming convention
        query_alt = query.replace("buyer_profiles", "buyer_preferences").replace("seller_profiles", "seller_properties")
        try:
            df = pd.read_sql_query(query_alt, conn)
            if not df.empty and 'phone_number' in df.columns:
                df['wa_link'] = df['phone_number'].apply(lambda p: generate_wa_link(p))
        except Exception as err:
            st.error(f"Error reading lead data: {err}")
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
        COALESCE(NULLIF(l.client_name, ''), 'Unknown') AS client_name,
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
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Combined Lead Intelligence", 
    "Visual Analytics & Insights", 
    "Inventory & Listings", 
    "Conversation Logs",
    "Auto-Match Engine"
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
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        total_leads = len(df)
        hot_leads = len(df[df['lead_tag'] == 'HOT']) if 'lead_tag' in df.columns else 0
        buyer_leads = len(df[df['intent'] == 'BUY']) if 'intent' in df.columns else 0
        seller_leads = len(df[df['intent'] == 'SELL']) if 'intent' in df.columns else 0
        both_leads = len(df[df['intent'] == 'BOTH']) if 'intent' in df.columns else 0

        kpi1.metric("Total Captured Leads", total_leads)
        kpi2.metric("🔥 Hot Leads", hot_leads)
        kpi3.metric("🏠 Buyers", buyer_leads)
        kpi4.metric("🏷️ Sellers", seller_leads)
        kpi5.metric("🔄 Dual (Buy & Sell)", both_leads)

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

        # --- SUB-TABS TO PREVENT HORIZONTAL SCROLLING ---
        sub_tab_buyer, sub_tab_seller, sub_tab_all = st.tabs([
            "Buyer Leads", 
            "Seller Listings", 
            "Quick Overview"
        ])

        selected_rows = []
        active_df = pd.DataFrame()

        # --- 1. BUYER SUB-TAB (5 Essential Columns) ---
        with sub_tab_buyer:
            buyer_df = filtered_df[filtered_df['intent'].isin(['BUY', 'BOTH', 'INQUERY'])].copy()
            
            buyer_columns = ['lead_id', 'client_name', 'phone_number', 'buyer_location', 'buyer_budget', 'wa_link']
            display_buyer_df = buyer_df[[c for c in buyer_columns if c in buyer_df.columns]]

            event_buyer = st.dataframe(
                display_buyer_df,
                use_container_width=True,
                column_order=["lead_id", "client_name", "phone_number", "buyer_location", 'buyer_land_area', "buyer_budget", "wa_link"],
                column_config={
                    "lead_id": st.column_config.NumberColumn("ID", width="small"),
                    "client_name": st.column_config.TextColumn("Client Name", width="medium"),
                    "phone_number": st.column_config.TextColumn("Phone", width="medium"),
                    "buyer_location": st.column_config.TextColumn("Location", width="medium"),
                    "buyer_land_area": st.column_config.TextColumn("Land Area", width="small"),
                    "buyer_budget": st.column_config.TextColumn("Budget", width="medium"),
                    "wa_link": st.column_config.LinkColumn("Action", display_text="Chat 💬", width="small")
                },
                on_select="rerun",
                selection_mode="single-row",
                key="df_buyers"
            )

            if event_buyer.selection.get("rows"):
                selected_rows = event_buyer.selection["rows"]
                active_df = display_buyer_df

        # --- 2. SELLER SUB-TAB (5 Essential Columns) ---
        with sub_tab_seller:
            seller_df = filtered_df[filtered_df['intent'].isin(['SELL', 'BOTH'])].copy()
            
            seller_columns = ['lead_id', 'client_name', 'phone_number', 'seller_mouza', 'seller_land_area', 'seller_asking_price', 'wa_link']
            display_seller_df = seller_df[[c for c in seller_columns if c in seller_df.columns]]

            event_seller = st.dataframe(
                display_seller_df,
                use_container_width=True,
                column_order=["lead_id", "client_name", "phone_number", "seller_mouza", "seller_asking_price", "wa_link"],
                column_config={
                    "lead_id": st.column_config.NumberColumn("ID", width="small"),
                    "client_name": st.column_config.TextColumn("Client Name", width="medium"),
                    "phone_number": st.column_config.TextColumn("Phone", width="medium"),
                    "seller_mouza": st.column_config.TextColumn("Mouza Location", width="medium"),
                    "seller_land_area": st.column_config.TextColumn("Land Area", width="medium"),
                    "seller_asking_price": st.column_config.TextColumn("Asking Price", width="medium"),
                    "wa_link": st.column_config.LinkColumn("Action", display_text="Chat 💬", width="small")
                },
                on_select="rerun",
                selection_mode="single-row",
                key="df_sellers"
            )

            if event_seller.selection.get("rows"):
                selected_rows = event_seller.selection["rows"]
                active_df = display_seller_df

        # --- 3. QUICK OVERVIEW SUB-TAB (6 Primary Columns) ---
        with sub_tab_all:
            overview_columns = ['lead_id', 'client_name', 'phone_number', 'intent', 'lead_tag', 'wa_link']
            display_overview_df = filtered_df[[c for c in overview_columns if c in filtered_df.columns]]

            event_all = st.dataframe(
                display_overview_df,
                use_container_width=True,
                column_order=["lead_id", "client_name", "phone_number", "intent", "lead_tag", "wa_link"],
                column_config={
                    "lead_id": st.column_config.NumberColumn("ID", width="small"),
                    "client_name": st.column_config.TextColumn("Client Name", width="medium"),
                    "phone_number": st.column_config.TextColumn("Phone", width="medium"),
                    "intent": st.column_config.SelectboxColumn("Intent", options=["BUY", "SELL", "BOTH", "INQUERY"], width="small"),
                    "lead_tag": st.column_config.SelectboxColumn("Tag", options=["HOT", "WARM", "COLD"], width="small"),
                    "wa_link": st.column_config.LinkColumn("Action", display_text="Chat 💬", width="small")
                },
                on_select="rerun",
                selection_mode="single-row",
                key="df_all"
            )

            if event_all.selection.get("rows"):
                selected_rows = event_all.selection["rows"]
                active_df = display_overview_df

        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            st.download_button(
                label="📥 Export Unified Leads to CSV",
                data=filtered_df.to_csv(index=False).encode('utf-8'),
                file_name='malik_property_unified_leads.csv',
                mime='text/csv',
                use_container_width=True
            )

        with col_dl2:
            st.download_button(
                label="📄 Export Unified Leads to PDF",
                data=generate_leads_pdf(filtered_df),
                file_name='malik_property_unified_leads.pdf',
                mime='application/pdf',
                use_container_width=True
            )

        # ---------------------------------------------------------
        # PRE-FORMATTED WHATSAPP QUICK RESPONSE TEMPLATES
        # ---------------------------------------------------------
        st.divider()
        st.subheader("Pre-formatted WhatsApp Quick Templates")

        if not selected_rows or active_df.empty:
            st.info("💡 **Tip:** Select any row in the tables above to auto-fill quick response templates for that lead.")
        else:
            lead = active_df.iloc[selected_rows[0]]
            
            client_name = lead.get('client_name', 'Valued Client')
            phone = lead.get('phone_number', '')
            location = lead.get('buyer_location') or lead.get('seller_mouza') or 'Mouza'
            budget = lead.get('buyer_budget') or lead.get('seller_asking_price') or 'your specified budget'
            prop_type = lead.get('buyer_property_type') or lead.get('seller_land_area') or 'property'

            st.markdown(f"**Selected Lead:** `{client_name}` | **Phone:** `{phone}`")

            col_tpl1, col_tpl2 = st.columns(2)

            # --- OPTION A: MATCHING PLOTS TEMPLATE ---
            with col_tpl1:
                st.markdown("#### 🎯 Option A: Matching Properties")
                
                msg_en = (
                    f"Assalam-o-Alaikum {client_name}, here are 3 plots matching your budget "
                    f"({budget}) in {location}:\n\n"
                    f"1. Top option in {location} ({prop_type})\n"
                    f"2. Commercial plot near main road\n"
                    f"3. Residential plot with clear title\n\n"
                    f"Let me know when you'd like to schedule a site visit!"
                )
                
                msg_ur = (
                    f"السلام علیکم {client_name} صاحب،\n"
                    f"آپ کے بجٹ ({budget}) کے مطابق موضہ {location} میں یہ 3 بہترین اپشنز موجود ہیں:\n\n"
                    f"1. پرائم لوکیشن پلاٹ - {location}\n"
                    f"2. کمرشل / رہائشی اپشن\n"
                    f"3. فلیٹ / کلیئر رجسٹری پلاٹ\n\n"
                    f"کیا آپ آج یا کل ان کا وزٹ کرنا چاہیں گے؟"
                )

                tab_en1, tab_ur1 = st.tabs(["English Template", "Urdu Template"])
                
                with tab_en1:
                    st.text_area("Preview (English)", msg_en, height=140, key="prev_en_1")
                    st.link_button(
                        "Launch WhatsApp (English)",
                        url=generate_wa_link(phone, msg_en),
                        type="primary",
                        use_container_width=True
                    )

                with tab_ur1:
                    st.text_area("Preview (Urdu)", msg_ur, height=140, key="prev_ur_1")
                    st.link_button(
                        "Launch WhatsApp (Urdu)",
                        url=generate_wa_link(phone, msg_ur),
                        type="primary",
                        use_container_width=True
                    )

            # --- OPTION B: INQUIRY FOLLOW-UP TEMPLATE ---
            with col_tpl2:
                st.markdown("#### 🔄 Option B: Inquiry Follow-up")
                
                msg_followup_en = (
                    f"Assalam-o-Alaikum {client_name},\n"
                    f"Following up on your inquiry regarding property in '{location}'. "
                    f"Are you still looking to finalize a deal this week?"
                )
                
                msg_followup_ur = (
                    f"السلام علیکم {client_name} صاحب،\n"
                    f"آپ کی انکوائری (موضہ {location}) کے حوالے سے فالو اپ کرنا تھا۔ "
                    f"کیا آپ اس ہفتے بات فائنل کرنا چاہتے ہیں؟"
                )

                tab_en2, tab_ur2 = st.tabs(["English Follow-up", "Urdu Follow-up"])

                with tab_en2:
                    st.text_area("Preview (English)", msg_followup_en, height=140, key="prev_en_2")
                    st.link_button(
                        "Launch WhatsApp Follow-Up",
                        url=generate_wa_link(phone, msg_followup_en),
                        type="secondary",
                        use_container_width=True
                    )

                with tab_ur2:
                    st.text_area("Preview (Urdu)", msg_followup_ur, height=140, key="prev_ur_2")
                    st.link_button(
                        "Launch WhatsApp Follow-Up (Urdu)",
                        url=generate_wa_link(phone, msg_followup_ur),
                        type="secondary",
                        use_container_width=True
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
            st.markdown("**Lead Conversion Funnel**")
            tag_counts = df_analytics['lead_tag'].value_counts() if 'lead_tag' in df_analytics.columns else pd.Series()
            
            funnel_stages = ["New Lead", "Hot Lead", "Warm Lead", "Cold Lead"]
            funnel_values = [
                len(df_analytics),
                tag_counts.get("HOT", 0),
                tag_counts.get("WARM", 0),
                tag_counts.get("COLD", 0)
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
            mouza_series = df_analytics['buyer_location'].fillna(df_analytics['seller_mouza']).dropna()
            
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

        # 3. Intent Distribution
        with col_chart3:
            st.markdown("**📊 Intent Breakdown (Buy vs Sell vs Both)**")
            if 'intent' in df_analytics.columns:
                intent_counts = df_analytics['intent'].value_counts().reset_index()
                intent_counts.columns = ['Intent', 'Count']
                fig_pie = px.pie(
                    intent_counts, 
                    names='Intent', 
                    values='Count', 
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_pie.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=350)
                st.plotly_chart(fig_pie, use_container_width=True)

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
        submitted = st.form_submit_button("Publish Property")
        
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
                    (title, property_type, intent_type, location_mouza, land_area, asking_price, ownership_type, doc_type, description, image_url, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'AVAILABLE')
                """, (title, property_type, intent_type, location_mouza, land_area, asking_price, ownership_type, doc_type, description, saved_image_path))
                conn.commit()
                conn.close()
                st.success(f"Property '{title}' added to active inventory!")
                st.rerun()
            else:
                st.error("Please fill in required fields (Title & Location).")

    st.divider()
    st.subheader("📦 Interactive Inventory Manager")
    st.caption("⚡ **Auto-Purge Feature Active:** Changing any item's status to **SOLD** directly in the table cell will immediately delete its database record and purge all associated media files from storage.")
    
    conn = get_db_connection()
    properties_df = pd.read_sql_query(
        "SELECT id, title, property_type, intent_type, location_mouza, land_area, asking_price, status, image_url, created_at FROM properties ORDER BY created_at DESC", 
        conn
    )
    conn.close()

    if properties_df.empty:
        st.info("No active properties found in inventory.")
    else:
        # Interactive table editor with dropdown cell for Status
        edited_inventory = st.data_editor(
            properties_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "title": st.column_config.TextColumn("Title", disabled=True, width="medium"),
                "property_type": st.column_config.TextColumn("Type", disabled=True, width="small"),
                "intent_type": st.column_config.TextColumn("Purpose", disabled=True, width="small"),
                "location_mouza": st.column_config.TextColumn("Mouza", disabled=True, width="medium"),
                "land_area": st.column_config.TextColumn("Area", disabled=True, width="small"),
                "asking_price": st.column_config.NumberColumn("Price (PKR)", format="PKR %d", disabled=True),
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["AVAILABLE", "PENDING", "SOLD"],
                    width="medium",
                    required=True,
                    help="Select SOLD to trigger automatic disk and media cleanup."
                ),
                "image_url": st.column_config.TextColumn("Media Path", disabled=True, width="medium"),
                "created_at": st.column_config.TextColumn("Created Date", disabled=True, width="small")
            },
            key="inventory_table_editor"
        )

        # Detect real-time updates in the Status dropdown
        for index, row in edited_inventory.iterrows():
            original_status = properties_df.loc[properties_df['id'] == row['id'], 'status'].values[0]
            new_status = row['status']

            # Trigger immediate purge on status change to 'SOLD'
            if new_status == "SOLD" and original_status != "SOLD":
                property_id = int(row['id'])
                
                # Execute deletion
                if delete_sold_property(property_id):
                    st.toast(f"🗑️ Property #{property_id} sold! Media purged and record deleted.", icon="✅")
                    st.rerun()
                else:
                    st.error(f"❌ Failed to purge media for property #{property_id}. Check terminal logs.")

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

# ================= ================= ================= =============
# TAB 5: CONVERSATION LOGS
# ================= ================= ================= =============
with tab5:
    st.header("🎯 Buyer ↔ Property Auto-Match Engine")
    st.caption("Instantly query inventory against buyer criteria to generate match scorecards and send WhatsApp proposals.")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query leads joined with buyer_preferences
    cursor.execute("""
        SELECT 
            l.id AS lead_id, 
            COALESCE(NULLIF(l.client_name, ''), 'Awaiting Name') AS client_name, 
            l.phone_number, 
            b.preferred_location, 
            b.property_type, 
            b.budget_range 
        FROM leads l
        JOIN buyer_preferences b ON l.id = b.lead_id
        ORDER BY l.id DESC
    """)
    buyers = cursor.fetchall()
    conn.close()

    if not buyers:
        st.info("No active buyers found in database yet.")
    else:
        buyer_options = {
            f"Lead #{b['lead_id']} - {b['client_name']} ({b['phone_number']})": b 
            for b in buyers
        }
        selected_label = st.selectbox("Select Buyer to Match:", list(buyer_options.keys()))
        selected_buyer = buyer_options[selected_label]

        # Display Selected Buyer Criteria Card
        st.markdown("### 📋 Buyer Criteria")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Client Name", selected_buyer["client_name"])
        col2.metric("Preferred Location", selected_buyer["preferred_location"] or "N/A")
        col3.metric("Property Type", selected_buyer["property_type"] or "N/A")
        col4.metric("Budget Range", selected_buyer["budget_range"] or "N/A")

        st.divider()

        # Run Auto-Match Engine
        top_matches = get_buyer_matches(selected_buyer["lead_id"])

        if not top_matches:
            st.warning("⚠️ No direct inventory matches found for this buyer's current preferences.")
        else:
            st.subheader(f"🔥 Top {len(top_matches)} Recommended Matches")

            for match in top_matches:
                with st.container():
                    m_col1, m_col2 = st.columns([3, 1])

                    with m_col1:
                        score = match["score"]
                        score_color = "🟢" if score >= 75 else ("🟡" if score >= 50 else "🟠")
                        st.markdown(f"### {score_color} {match['title']} — **{score}% Match**")
                        
                        st.write(f"📍 **Location:** {match['location']} | 🏗️ **Type:** {match['property_type']}")
                        st.write(f"💰 **Asking Price:** {match['price']} | 📐 **Area:** {match['area']}")
                        st.caption(f"✨ **Match Highlights:** {', '.join(match['reasons'])}")

                    with m_col2:
                        client_name = selected_buyer["client_name"]
                        proposal_text = (
                            f"Assalam-o-Alaikum {client_name}! 🌟\n\n"
                            f"Based on your requirements, here is a property matching your criteria at Malik Property Mianwali:\n\n"
                            f"🏠 *{match['title']}*\n"
                            f"📍 Location: {match['location']}\n"
                            f"🏗️ Type: {match['property_type']}\n"
                            f"📐 Area: {match['area']}\n"
                            f"💰 Price: {match['price']}\n\n"
                            f"Would you like to schedule a site visit or view the documents?"
                        )

                        clean_phone = format_pk_phone(selected_buyer["phone_number"])
                        wa_url = generate_wa_link(clean_phone, proposal_text)

                        st.markdown("<br>", unsafe_allow_html=True)
                        st.link_button(
                            "📲 Send Proposal via WhatsApp", 
                            wa_url, 
                            type="primary", 
                            use_container_width=True
                        )

                st.divider()

if due_leads:
    with st.container():
        st.error(f"🚨 **ACTION REQUIRED:** {len(due_leads)} Lead(s) Need Follow-Up Today or Are Overdue!")
        
        with st.expander("📋 View Leads Due Today"):
            for lead in due_leads:
                col_info, col_act = st.columns([3, 1])
                with col_info:
                    st.markdown(
                        f"👤 **{lead['client_name']}** (`{lead['phone_number']}`) | "
                        f"Tag: **{lead['lead_tag'] or 'N/A'}** | Stage: **{lead['lead_stage']}** | "
                        f"📅 Due: `{lead['next_contact_date']}`"
                    )
                with col_act:
                    followup_text = f"Assalam-o-Alaikum {lead['client_name']}! Following up from Malik Property Mianwali regarding your property inquiry. How can we assist you today?"
                    clean_phone = format_pk_phone(lead['phone_number'])
                    wa_url = generate_wa_link(clean_phone, followup_text)
                    st.link_button("💬 WhatsApp Follow-Up", wa_url, use_container_width=True)
st.divider()

# =========================================================
# 📊 2. LEAD PIPELINE DATA EDITOR
# =========================================================
st.subheader("📌 Lead Pipeline & Follow-Up Manager")
st.caption("Manage stages, schedule follow-up dates, and track sales progression in real time.")

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("""
    SELECT 
        id, 
        COALESCE(NULLIF(client_name, ''), 'Awaiting Name') AS client_name, 
        phone_number, 
        COALESCE(intent, 'INQUERY') AS intent, 
        COALESCE(lead_tag, 'COLD') AS lead_tag, 
        COALESCE(lead_stage, 'New Inquiry') AS lead_stage,
        next_contact_date
    FROM leads
    ORDER BY id DESC
""")
raw_leads = cursor.fetchall()
conn.close()

if raw_leads:
    df_leads = pd.DataFrame([dict(r) for r in raw_leads])
    
    # Convert string dates to datetime for st.data_editor datepicker
    df_leads["next_contact_date"] = pd.to_datetime(df_leads["next_contact_date"]).dt.date

    STAGE_OPTIONS = [
        "New Inquiry",
        "Site Visit Scheduled",
        "Token Given / Bayana",
        "Closed Deal"
    ]

    # Render st.data_editor with DatePicker & Stage Selectbox
    edited_df = st.data_editor(
        df_leads,
        column_config={
            "id": st.column_config.NumberColumn("Lead ID", disabled=True),
            "client_name": "Client Name",
            "phone_number": st.column_config.TextColumn("Phone", disabled=True),
            "intent": st.column_config.TextColumn("Intent", disabled=True),
            "lead_tag": st.column_config.TextColumn("Tag", disabled=True),
            "lead_stage": st.column_config.SelectboxColumn(
                "Pipeline Stage",
                options=STAGE_OPTIONS,
                required=True,
                help="Track the progression of this lead"
            ),
            "next_contact_date": st.column_config.DateColumn(
                "Next Contact Date",
                help="Set a reminder date for agent follow-up",
                format="YYYY-MM-DD"
            )
        },
        use_container_width=True,
        hide_index=True,
        key="lead_pipeline_editor"
    )

    # Save edits back to SQLite when user makes changes in the editor table
    if st.button("💾 Save Pipeline Updates", type="primary"):
        for _, row in edited_df.iterrows():
            lead_id = int(row["id"])
            contact_date = str(row["next_contact_date"]) if pd.notnull(row["next_contact_date"]) else None
            stage = row["lead_stage"]
            update_lead_pipeline(lead_id, contact_date, stage)
        
        st.success("✅ Pipeline stages and follow-up dates updated successfully!")
        st.rerun()
else:
    st.info("No leads available in the pipeline.")