import streamlit as st
import pandas as pd

# 1. Setup the Web Page
st.set_page_config(page_title="NXP Cross-Reference Tool", layout="wide")
st.title("🔄 NXP RTC Cross-Reference Search")
st.write("Enter a competitor part number below to find the best NXP equivalent.")

st.subheader("Definition of the Cross-Grade")
st.badge("Grade A 🟢 : Drop-In Replacement", color="green") 
st.caption("Exact match on Interface, package, pinout, supply voltage, and core features.")
st.badge("Grade B 🟡: Functional Equivalent", color="yellow") 
st.caption("Same interface, highly similar package, and matching critical features")
st.badge("Grade C 🟠: Alternative / Downgrade", color="orange") 
st.caption("Same interface and similar package, but differs in features")

# 2. Load the Databases 
# (The @st.cache_data makes the app load instantly after the first time)
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

# 3. THE SEARCH BAR
search_query = st.text_input("Search Competitor Part (e.g., MAX31341C):", value="")

# 4. Run the Engine when someone searches
if search_query:
    # Clean up the input so it's not case-sensitive
    search_query = search_query.strip().upper() 
    
    # Look for the part in the Analog database
    match_part = df_competitor[df_competitor['Part number'].str.strip().str.upper() == search_query]
    
    if match_part.empty:
        st.warning(f"Could not find '{search_query}' in the competitor database. Please check the spelling.")
    else:
        target_part = match_part.iloc[0]
        st.success(f"✅ Found Competitor Part: **{target_part['Part number']}**")
        
        # Package Alias Dictionary
        package_mapping = {
            'TDFN10': ['HXSON10', 'HVSON10'],
            'WLP12': ['WLCSP12']
        }
        
        results = []
        
        # The Scoring Engine
        for index, nxp_part in df_nxp.iterrows():
            score = 0
            
            #package type
            target_pkg = str(target_part['Package type']).strip()
            nxp_pkg = str(nxp_part['Package type']).strip()
            
            if target_pkg == nxp_pkg:
                score += 40
            elif target_pkg in package_mapping and nxp_pkg in package_mapping[target_pkg]:
                score += 40
                
            #interface type    
            target_protocol = str(target_part['Communication Protocol']).strip()
            nxp_protocol = str(nxp_part['Communication Protocol']).strip()
            if target_protocol in nxp_protocol or nxp_protocol in target_protocol: 
                score += 30
                
            #features   
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
                
                
            # Assign visual badges for the UI
            if score == 100: grade = 'Grade A - Drop-In 🟢'
            elif score >= 70: grade = 'Grade B - Functional Equivalent 🟡'
            elif score >= 40: grade = 'Grade C - Alternative 🟠'
            else: grade = 'No Match'
                
            if score >= 50:
                results.append({
                    'NXP Replacement': nxp_part['Part number'],
                    'Compatibility': grade,
                    'Match Score': score,
                    'Package': nxp_pkg,
                    'Supply Voltage (V)': nxp_part['Supply Voltage [Min to Max] (V)'],
                    'Supply Current (uA)': nxp_part['Low supply current (uA)'],
                    'Interface': nxp_protocol, 
                    'Baudrate (kHz)': nxp_part['Baudrate'],
                    'Operating Temperature (C)': nxp_part['Operating Temperature (℃)']
                })
        
        # 5. Display the Results in a clean table
        if results:
            results_df = pd.DataFrame(results).sort_values(by='Match Score', ascending=False)
            st.write("### Recommended NXP Replacements")
            
            # Display as a clean, interactive web table
            st.dataframe(
                results_df, 
                use_container_width=True, 
                hide_index=True 
            )
        else:
            st.info("No suitable NXP replacements found for this part.")
