import pandas as pd
import argparse

def main(my_csv, other_csv):
    # Read your CSV file (assumes columns: bug-id, path, rank)
    df_my = pd.read_csv(my_csv)
    
    # Read the other researcher's CSV (assumes columns: bug-id, path, rank)
    df_other = pd.read_csv(other_csv)
    
    # Merge the two DataFrames on 'bug-id' and 'path'
    # Suffixes _my and _other denote the source of the rank values.
    merged = pd.merge(df_my, df_other, on=["bug-id", "path"], suffixes=("_my", "_other"))
    
    # Check that the 'rank' columns are numeric; if not, try converting them
    merged['rank_my'] = pd.to_numeric(merged['rank_my'], errors='coerce')
    merged['rank_other'] = pd.to_numeric(merged['rank_other'], errors='coerce')
    
    # Remove any rows with NaN in either rank
    merged = merged.dropna(subset=['rank_my', 'rank_other'])
    
    # Count the rows where your rank is equal to or lower (i.e., as good as or better) than the other researcher's rank.
    count = (merged['rank_my'] <= merged['rank_other']).sum()
    
    print("Number of bugs where your rank is at or below the other researcher's rank:", count)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare two CSV files for bug rankings and count how many of your bug results are at or below the other researcher's ranking."
    )
    parser.add_argument("my_csv", help="Path to your CSV file (e.g., 0225252354.csv)")
    parser.add_argument("other_csv", help="Path to the other researcher's CSV file")
    
    args = parser.parse_args()
    main(args.my_csv, args.other_csv)
