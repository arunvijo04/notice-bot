import requests
from bs4 import BeautifulSoup
import sqlite3
from twilio.rest import Client
from flask import Flask, jsonify
import datetime
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Twilio credentials (use your own)
TWILIO_SID = os.getenv('TWILIO_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
WHATSAPP_FROM = os.getenv('WHATSAPP_FROM')  # Twilio sandbox number

# Connect to SQLite DB
conn = sqlite3.connect('notices.db', check_same_thread=False)
c = conn.cursor()

# Create tables if not exist
c.execute('''CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                date TEXT,
                link TEXT UNIQUE
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT UNIQUE
            )''')
conn.commit()

def fetch_notices():
    url = "https://www.rajagiritech.ac.in/home/notice/Notice.asp?NC=1"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table_rows = soup.select('table tr')[1:]

    new_notices = []
    for row in table_rows:
        cols = row.find_all('td')
        if len(cols) >= 2:
            date = cols[0].text.strip()
            title = cols[1].text.strip()
            link_tag = cols[1].find('a')
            link = "https://www.rajagiritech.ac.in/home/notice/" + link_tag['href'] if link_tag else ""
            
            # Check if already exists
            c.execute("SELECT * FROM notices WHERE link = ?", (link,))
            if not c.fetchone():
                c.execute("INSERT INTO notices (title, date, link) VALUES (?, ?, ?)", (title, date, link))
                conn.commit()
                new_notices.append({'title': title, 'date': date, 'link': link})
    return new_notices

def send_whatsapp(to, body):
    client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=body,
        from_=WHATSAPP_FROM,
        to=f'whatsapp:{to}'
    )
    return message.sid

def notify_students(notices):
    c.execute("SELECT phone FROM students")
    students = c.fetchall()
    for notice in notices:
        msg = f"[New Notice]\n{notice['title']}\nDate: {notice['date']}\nLink: {notice['link']}"
        for student in students:
            try:
                send_whatsapp(student[0], msg)
            except Exception as e:
                print(f"Failed to send to {student[0]}: {e}")

@app.route('/scan', methods=['GET'])
def scan():
    notices = fetch_notices()  # Fetch new notices
    if notices:
        notify_students(notices)  # Notify students if there are new notices
    
    # Fetch the latest notice
    c.execute("SELECT title, date, link FROM notices ORDER BY id DESC LIMIT 1")
    latest_notice = c.fetchone()
    if latest_notice:
        # Construct the message for the latest notice
        msg = f"[New Notice]\n{latest_notice[0]}\nDate: {latest_notice[1]}\nLink: {latest_notice[2]}"
        
        # Send to a registered phone number (replace with a valid number in format "+123456789")
        send_whatsapp("+919496097469", msg)  # Replace this with the actual registered phone number

    return jsonify({'new_notices': notices})


@app.route('/notices', methods=['GET'])
def get_notices():
    c.execute("SELECT title, date, link FROM notices ORDER BY id DESC")
    rows = c.fetchall()
    return jsonify([{'title': r[0], 'date': r[1], 'link': r[2]} for r in rows])

@app.route('/register/<name>/<phone>', methods=['GET'])
def register(name, phone):
    try:
        c.execute("INSERT INTO students (name, phone) VALUES (?, ?)", (name, phone))
        conn.commit()
        return jsonify({'status': 'registered'})
    except sqlite3.IntegrityError:
        return jsonify({'status': 'already exists'})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
