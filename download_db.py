"""Downloads the Chinook SQLite sample database into data/chinook.sqlite."""
import urllib.request

from text2sql.config import DATA_DIR

URL = ("https://github.com/lerocha/chinook-database/raw/master/"
       "ChinookDatabase/DataSources/Chinook_Sqlite.sqlite")

if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    dest = DATA_DIR / "chinook.sqlite"
    if dest.exists():
        print(f"{dest} already exists.")
    else:
        print("Downloading Chinook ...")
        urllib.request.urlretrieve(URL, dest)
        print(f"Saved to {dest} ({dest.stat().st_size / 1024:.0f} KB)")
