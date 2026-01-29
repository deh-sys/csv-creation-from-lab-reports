import pandas as pd

try:
    df = pd.read_excel("output_excel/lab_results.xlsx")
    
    print("\n--- Unique Component Names ---")
    unique_components = sorted(df['Component'].astype(str).unique())
    for comp in unique_components:
        print(comp)

except Exception as e:
    print(f"Error: {e}")

