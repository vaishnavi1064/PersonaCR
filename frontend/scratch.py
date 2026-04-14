import urllib.request
import json

url = "https://srgpyqlzdqhjftzpvesi.supabase.co/auth/v1/settings" # a public unauthenticated endpoint that requires anon key
headers = {
    "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNyZ3B5cWx6ZHFoamZ0enB2ZXNpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU2NjYzOTYsImV4cCI6MjA5MTI0MjM5Nn0.wnKsLdLO6U3ofMLv2FVOGs8dz90EkKnqQCc9VL7rFtc"
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        print("Status:", response.status)
        print("Response:", response.read().decode())
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code)
    print("Error Response:", e.read().decode())
