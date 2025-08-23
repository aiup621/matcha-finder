from dotenv import load_dotenv; load_dotenv()
import os, requests
key=os.getenv("GOOGLE_API_KEY"); cx=os.getenv("GOOGLE_CSE_ID")
print("GOOGLE_API_KEY set?:", bool(key))
print("GOOGLE_CSE_ID     :", cx)
r=requests.get("https://www.googleapis.com/customsearch/v1",
               params={"key":key,"cx":cx,"q":"matcha cafe CA","num":1}, timeout=15)
print("HTTP", r.status_code, r.json().get("searchInformation",{}))