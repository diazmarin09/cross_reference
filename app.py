import streamlit as st
import pandas as pd

# 1. Setup the Web Page
st.set_page_config(page_title="NXP Cross-Reference Tool", layout="wide", page_icon="nxp_logo.png") 

try:
    st.image("nxp_logo.png", width=120)
except FileNotFoundError:
    st.write("🖼️ Logo")

st.title("RTC Cross-Reference Search")
st.write("Enter a competitor part number or an NXP EOL part number below to find the best NXP equivalent.")

st.subheader("Definition of the Cross-Grade")



# Display Grades definitions
col1, col2 = st.columns([1, 4])
with col1:
    st.badge("Grade A 🟢: Functional Replacement", color="green")
with col2:
    st.caption("Exact match on Interface, package, pin count, supply voltage, and core features.")

col1, col2 = st.columns([1, 4])
with col1:
    st.badge("Grade B 🟡: Near Replacement", color="orange")
with col2:
    st.caption("Minor differences that may require validation.")

col1, col2 = st.columns([1, 4])
with col1:
    st.badge("Grade C 🔴: Partial Replacement", color="red")
with col2:
    st.caption("Significant differences requiring redesign or qualification.")



# 2. Load the Databases 
@st.cache_data
def load_data():
    df_competitor = pd.read_csv('RTC Cross Reference.xlsx - Competitors.csv')
    df_nxp = pd.read_csv('RTC Cross Reference.xlsx - NXP.csv')
    df_competitor.columns = df_competitor.columns.str.strip()
    df_nxp.columns = df_nxp.columns.str.strip()
    return df_competitor, df_nxp

try:
    df_competitor, df_nxp = load_data()
except FileNotFoundError:
    st.error("⚠️ Databases not found. Please ensure the CSV files are in the same folder as this script.")
    st.stop()



# 3. The search bar (Autocomplete)
part_list = df_competitor['Part number'].dropna().astype(str).str.strip().sort_values().tolist()

search_query = st.selectbox(
    "Search Competitor Part (Start typing to auto-complete):",
    options=[""] + part_list,
    index=0
)




# 4. Run the Engine when someone selects a part
if search_query != "":
    search_query = search_query.strip().upper() 
    match_part = df_competitor[df_competitor['Part number'].str.strip().str.upper() == search_query]
    
    if match_part.empty:
        st.warning(f"Could not find '{search_query}' in the competitor database. Please check the spelling.")
    else:
        target_part = match_part.iloc[0]
        st.success(f"✅ Found Competitor Part: **{target_part['Part number']}**")
        
        results = []
        target_type = str(target_part['RTC Type']).strip().upper()
        
        # Scoring Engine
        for index, nxp_part in df_nxp.iterrows():
            nxp_type = str(nxp_part['RTC Type']).strip().upper()
            
            # THE HARD FILTER: Skip if type doesn't match
            if target_type != nxp_type:
                continue 
                
            score = 0
            
            # Package match (40 pts)
            target_pkg = str(target_part['Package type']).strip()
            nxp_pkg = str(nxp_part['Package type']).strip()
            if target_pkg == nxp_pkg:
                score += 40
                
            # Protocol match (30 pts)
            target_protocol = str(target_part['Communication Protocol']).strip()
            nxp_protocol = str(nxp_part['Communication Protocol']).strip()
            if target_protocol in nxp_protocol or nxp_protocol in target_protocol: 
                score += 30
                
            # Feature updates (5 pts each)
            if str(target_part['Supply Voltage [Min to Max] (V)']).strip() == str(nxp_part['Supply Voltage [Min to Max] (V)']).strip():
                score += 5
            if str(target_part['Low supply current (uA)']).strip() == str(nxp_part['Low supply current (uA)']).strip():
                score += 5
            if str(target_part['Battery Back Up']).strip() == str(nxp_part['Battery Back Up']).strip():
                score += 5
            if str(target_part['SRAM']).strip() == str(nxp_part['SRAM']).strip():
                score += 5
            if str(target_part['Programmable alarm']).strip() == str(nxp_part['Programmable alarm']).strip():
                score += 5
            if str(target_part['Operating Temperature (℃)']).strip() == str(nxp_part['Operating Temperature (℃)']).strip():
                score += 5
                
            # Grade Mapping aligned with definitions UI
            if score == 100: 
                grade = 'Grade A - Functional Replacement 🟢'
            elif score >= 70: 
                grade = 'Grade B - Near Replacement 🟡'
            elif score >= 30: 
                grade = 'Grade C - Partial Replacement 🔴'
            else: 
                grade = 'No Match'
                
            if score >= 30:
                results.append({
                    'NXP Replacement': nxp_part['Part number'],
                    'Datasheet': nxp_part['Datasheet'],
                    'Type': nxp_part['RTC Type'],
                    'Compatibility': grade,
                    'Match Score': score,
                    'Package': nxp_pkg,
                    'Supply Voltage (V)': nxp_part['Supply Voltage [Min to Max] (V)'],
                    'Supply Current (uA)': nxp_part['Low supply current (uA)'],
                    'Interface': nxp_protocol, 
                    'Operating Temp (C)': nxp_part['Operating Temperature (℃)']
                })           
        
        
        
        # 5. Display the Results
        if results:
            results_df = pd.DataFrame(results).sort_values(by='Match Score', ascending=False)
            
            if target_type == 'IC':
                results_df = results_df.head(5)
                
            st.write("### Recommended NXP Replacements")
            
            SHOW_INTERNAL_SCORE = False 
            display_df = results_df.copy()
            if not SHOW_INTERNAL_SCORE:
                display_df = display_df.drop(columns=['Match Score'])
            
            st.dataframe(
                display_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Datasheet": st.column_config.LinkColumn(
                        "Datasheet",
                        help="Click to open the NXP datasheet",
                        display_text="View PDF" 
                    )
                }
            )
            
            # ---------------------------------------------------------
            # COMPARISON TABLE (COMPETITOR VS NXP TOP 1 & TOP 2)
            # ---------------------------------------------------------
            st.divider()
            st.write("### Comparison Table (Top 2 Matches)")
            
            # Base features list
            features_list = [
                "Supplier", "Type", "Package", "Interface", "Baudrate (KHz)",
                "Voltage [Min-Max] (V)", "Low Supply Current (uA)", "Battery Back Up",
                "SRAM", "Watchdog timer", "Tamper inputs", "Programmable Alarm",
                "Automotive grade", "Operating Temp (℃)"
            ]
            
            # Build up the structural dataset starting with the feature list and competitor part
            comp_data = {
                "Feature": features_list,
                f"{target_part['Part number']} (Competitor)": [
                    str(target_part.get('Supplier', '-')),
                    str(target_part.get('RTC Type', '-')),
                    str(target_part.get('Package type', '-')),
                    str(target_part.get('Communication Protocol', '-')),
                    str(target_part.get('Baudrate', '-')),
                    str(target_part.get('Supply Voltage [Min to Max] (V)', '-')),
                    str(target_part.get('Low supply current (uA)', '-')),
                    str(target_part.get('Battery Back Up', '-')),
                    str(target_part.get('SRAM', '-')),
                    str(target_part.get('Watchdog Timer', '-')),
                    str(target_part.get('Tamper input', '-')),
                    str(target_part.get('Programmable alarm', '-')),
                    str(target_part.get('AEC-Q100 compliant', '-')),
                    str(target_part.get('Operating Temperature (℃)', '-'))
                ]
            }
            
            # Extract and add Top 1 NXP Match
            top1_nxp_name = results_df.iloc[0]['NXP Replacement']
            top1_nxp_part = df_nxp[df_nxp['Part number'] == top1_nxp_name].iloc[0]
            
            comp_data[f"{top1_nxp_part['Part number']} (Top 1)"] = [
                    str(top1_nxp_part.get('Supplier', '-')),
                    str(top1_nxp_part.get('RTC Type', '-')),
                    str(top1_nxp_part.get('Package type', '-')),
                    str(top1_nxp_part.get('Communication Protocol', '-')),
                    str(top1_nxp_part.get('Baudrate', '-')),
                    str(top1_nxp_part.get('Supply Voltage [Min to Max] (V)', '-')),
                    str(top1_nxp_part.get('Low supply current (uA)', '-')),
                    str(top1_nxp_part.get('Battery Back Up', '-')),
                    str(top1_nxp_part.get('SRAM', '-')),
                    str(top1_nxp_part.get('Watchdog Timer', '-')),
                    str(top1_nxp_part.get('Tamper input', '-')),
                    str(top1_nxp_part.get('Programmable alarm', '-')),
                    str(top1_nxp_part.get('AEC-Q100 compliant', '-')),
                    str(top1_nxp_part.get('Operating Temperature (℃)', '-'))
            ]
            
            # Check if a second match exists, extract and add it dynamically
            if len(results_df) > 1:
                top2_nxp_name = results_df.iloc[1]['NXP Replacement']
                top2_nxp_part = df_nxp[df_nxp['Part number'] == top2_nxp_name].iloc[0]
                
                comp_data[f"{top2_nxp_part['Part number']} (Top 2)"] = [
                    str(top2_nxp_part.get('Supplier', '-')),
                    str(top2_nxp_part.get('RTC Type', '-')),
                    str(top2_nxp_part.get('Package type', '-')),
                    str(top2_nxp_part.get('Communication Protocol', '-')),
                    str(top2_nxp_part.get('Baudrate', '-')),
                    str(top2_nxp_part.get('Supply Voltage [Min to Max] (V)', '-')),
                    str(top2_nxp_part.get('Low supply current (uA)', '-')),
                    str(top2_nxp_part.get('Battery Back Up', '-')),
                    str(top2_nxp_part.get('SRAM', '-')),
                    str(top2_nxp_part.get('Watchdog Timer', '-')),
                    str(top2_nxp_part.get('Tamper input', '-')),
                    str(top2_nxp_part.get('Programmable alarm', '-')),
                    str(top2_nxp_part.get('AEC-Q100 compliant', '-')),
                    str(top2_nxp_part.get('Operating Temperature (℃)', '-'))
                ]
            
            comp_df = pd.DataFrame(comp_data)
            st.dataframe(comp_df, use_container_width=True, hide_index=True)
            
        else:
            st.info(f"No suitable NXP {target_type.title()} replacements found for this part.")

# 6. Disclaimer
st.caption("Disclaimer: The cross-reference information provided by this tool is intended for reference purposes only. Customers are responsible for performing their own evaluation and comparison of the suggested devices to ensure suitability for their specific application. It is strongly recommended to review the latest datasheets, specifications, and technical documentation for each device before making any replacement or design decision. Compatibility, performance, and functionality should be independently verified by the customer.")