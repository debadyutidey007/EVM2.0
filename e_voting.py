import os
import re
import logging
import hashlib
import mysql.connector
import pandas as pd
import plotly.express as px
import pyotp
import time
import secrets
import smtplib
import json
from email.message import EmailMessage
from datetime import datetime
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify
import openai

# Load environment variables and set up Flask
load_dotenv("file1.env")
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# File for chatbot conversation history
CHAT_HISTORY_FILE = "chat_history.json"

# Set Up Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    filename='evoting_system.log',
    filemode='a'
)

# Blockchain and audit_log simulation
blockchain = []
audit_logs = []

# Database Connection
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
        return connection
    except mysql.connector.Error as err:
        logging.error(f"Database connection error: {err}")
        return None

# OTP Generator
def generate_otp(length: int = 6) -> str:
    return ''.join(str(secrets.randbelow(10)) for _ in range(length))

def is_valid_email(email: str) -> tuple[bool, str]:
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    known_domains = {
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", 
        "icloud.com", "aol.com", "protonmail.com"
    }
    
    if not re.fullmatch(email_regex, email):
        return False, "Please enter a valid email address"
    
    domain = email.split('@')[-1]
    if domain not in known_domains:
        return False, f"Unknown email service provider. We accept: {', '.join(sorted(known_domains))}"
    
    return True, ""

def send_otp_email(receiver_email, otp):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    
    is_valid, message = is_valid_email(receiver_email)
    if not is_valid:
        print(f"Error: {message}")
        return False
    
    msg = EmailMessage()
    msg["Subject"] = "Your OTP for Verification"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg.set_content(f"Your OTP for verification is: {otp}")
    
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def ensure_voter_identifier_column():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SHOW COLUMNS FROM voters LIKE 'voter_identifier'")
            result = cur.fetchone()
            if not result:
                cur.execute("ALTER TABLE voters ADD COLUMN voter_identifier VARCHAR(100) NOT NULL AFTER voter_username")
                conn.commit()
                logging.debug("voter_identifier column added to voters table.")
        except Exception as e:
            logging.error(f"Error ensuring voter_identifier column: {e}")
        finally:
            cur.close()
            conn.close()

def create_admins_table():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    admin_id INT AUTO_INCREMENT PRIMARY KEY,
                    admin_username VARCHAR(255) NOT NULL UNIQUE,
                    Password VARCHAR(255) NOT NULL,
                    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
            """)
            conn.commit()
            logging.debug("Admins table ensured to exist.")
        except Exception as e:
            logging.error(f"Error creating admins table: {e}")
        finally:
            cur.close()
            conn.close()

def remove_unique_constraint_on_username():
    """
    Drops any unique index on the voter_username column so that multiple voters can have the same username.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SHOW INDEX FROM voters WHERE Column_name='voter_username' AND Non_unique=0")
            index_info = cur.fetchone()
            if index_info:
                index_name = index_info[2]
                cur.execute(f"ALTER TABLE voters DROP INDEX {index_name}")
                conn.commit()
                logging.debug("Unique constraint on voter_username dropped.")
        except Exception as e:
            logging.error(f"Error dropping unique constraint on voter_username: {e}")
        finally:
            cur.close()
            conn.close()

ensure_voter_identifier_column()
create_admins_table()
remove_unique_constraint_on_username()

# Input Validation and Helper Functions
def is_valid_input(text: str) -> bool:
    return re.fullmatch(r'[A-Za-z0-9 ]+', text) is not None

def is_valid_voter_id(voter_id: str) -> bool:
    return re.fullmatch(r'\d{11}', voter_id) is not None

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def hash_vote(voter_id: str, candidate_id: str) -> str:
    vote_string = f"{voter_id}-{candidate_id}-{datetime.now()}"
    return hashlib.sha256(vote_string.encode()).hexdigest()

def add_to_blockchain(voter_id: str, username: str, candidate_id: str, candidate_name: str) -> dict:
    vote_hash = hash_vote(voter_id, candidate_id)
    block = {
        "index": len(blockchain) + 1,
        "timestamp": datetime.now().isoformat(),
        "voter_username": username,
        "voter_id": voter_id,
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "vote_hash": vote_hash,
    }
    blockchain.append(block)
    logging.debug(f"Block added to blockchain: {block}")
    return block

def log_action(action: str, details: str):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details
    }
    audit_logs.append(log_entry)
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            query = "INSERT INTO audit_logs (user_id, action, details, log_timestamp) VALUES (%s, %s, %s, %s)"
            user_id = session.get("user", {}).get("voter_id")
            cur.execute(query, (user_id, action, details, datetime.now()))
            conn.commit()
        except Exception as e:
            logging.error(f"Error logging action: {e}")
        finally:
            cur.close()
            conn.close()

def voter_id_exists(voter_id: str) -> bool:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            query = "SELECT COUNT(*) FROM voters WHERE voter_identifier = %s"
            cur.execute(query, (voter_id,))
            count = cur.fetchone()[0]
            return count > 0
        except Exception as e:
            logging.error(f"Error checking voter ID: {e}")
            return False
        finally:
            cur.close()
            conn.close()
    return False

def register_voter(username: str, voter_identifier: str, email: str, secret_key: str) -> bool:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            query = """
                INSERT INTO voters (voter_username, full_name, voter_identifier, email, otp_secret)
                VALUES (%s, %s, %s, %s, %s)
            """
            cur.execute(query, (username, username, voter_identifier, email, secret_key))
            conn.commit()
            return True
        except Exception as e:
            flash(f"Voter Registration error: {e}", "error")
            return False
        finally:
            cur.close()
            conn.close()
    return False

# Voter Login
def login_voter(username: str, provided_voter_identifier: str, otp_provided=None) -> dict:
    username = username.strip()
    if not is_valid_input(username) or not is_valid_voter_id(provided_voter_identifier):
        flash("Invalid login credentials.", "error")
        return {}
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            query = """
                SELECT voter_id, voter_username, voter_identifier, otp_secret
                FROM voters 
                WHERE voter_username = %s AND voter_identifier = %s
            """
            cur.execute(query, (username, provided_voter_identifier))
            user_record = cur.fetchone()
            if user_record:
                otp_secret = user_record["otp_secret"]
                totp = pyotp.TOTP(otp_secret, interval=60)
                if otp_provided is None:
                    otp = totp.now()
                    flash(f"Your OTP for login: {otp}", "info")
                    return {
                        "otp_pending": True,
                        "prefilled_username": username,
                        "prefilled_voter_identifier": provided_voter_identifier
                    }
                else:
                    if totp.verify(otp_provided, valid_window=1):
                        flash(f"Login successful! Welcome {username}.", "success")
                        return user_record
                    else:
                        flash("Invalid OTP! Login failed.", "error")
                        return {}
            else:
                flash("User not found.", "error")
                return {}
        except Exception as e:
            flash(f"Voter Login error: {e}", "error")
            return {}
        finally:
            cur.close()
            conn.close()
    return {}

def login_admin(username: str, password: str) -> dict:
    username = username.strip()
    if not is_valid_input(username):
        return {}
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            query = "SELECT admin_id, admin_username, Password FROM admins WHERE admin_username = %s"
            cur.execute(query, (username,))
            admin_record = cur.fetchone()
            if admin_record and password == admin_record["Password"]:
                logging.debug(f"Admin login successful: {username}")
                return admin_record
            else:
                return {}
        except Exception as e:
            logging.error(f"Admin Login error: {e}")
            return {}
        finally:
            cur.close()
            conn.close()
    return {}

# ------------------------------------------------------------------------------
# Fetching Data for Dynamic Dropdowns
# ------------------------------------------------------------------------------
def fetch_states() -> list:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT state_id, state_name FROM states")
            states = cur.fetchall()
            return states
        except Exception as e:
            logging.error(f"Error fetching states: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def fetch_regions_by_state(state_id: int) -> list:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT region_id, region_name FROM regions WHERE state_id = %s", (state_id,))
            regions = cur.fetchall()
            return regions
        except Exception as e:
            logging.error(f"Error fetching regions: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def fetch_constituencies_by_region(region_id: int) -> list:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT constituency_id, constituency_name FROM constituencies WHERE region_id = %s", (region_id,))
            constituencies = cur.fetchall()
            return constituencies
        except Exception as e:
            logging.error(f"Error fetching constituencies: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def fetch_candidates_by_constituency(constituency_id: int) -> list:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT candidate_id, candidate_name, party FROM candidates WHERE constituency_id = %s", (constituency_id,))
            candidates = cur.fetchall()
            return candidates
        except Exception as e:
            logging.error(f"Error fetching candidates: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

# ------------------------------------------------------------------------------
# Vote Handling
# ------------------------------------------------------------------------------
def save_vote_to_db(voter_id: int, candidate_id: int, election_id: int, constituency_id: int, vote_hash: str):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            query = """
                INSERT INTO votes (voter_id, candidate_id, election_id, constituency_id, vote_timestamp, vote_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            values = (voter_id, candidate_id, election_id, constituency_id, datetime.now(), vote_hash)
            cur.execute(query, values)
            conn.commit()
        except Exception as e:
            logging.error(f"Error saving vote: {e}")
        finally:
            cur.close()
            conn.close()

def get_current_election() -> dict:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT election_id, election_name FROM elections WHERE status = 'ongoing' LIMIT 1")
            election = cur.fetchone()
            return election if election else {}
        except Exception as e:
            logging.error(f"Error fetching election: {e}")
            return {}
        finally:
            cur.close()
            conn.close()
    return {}

def handle_vote(voter: dict, candidate: dict, constituency_id: int) -> bool:
    election = get_current_election()
    if not election:
        return False
    voter_id = voter["voter_id"]
    election_id = election["election_id"]

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            query = "SELECT COUNT(*) FROM votes WHERE voter_id = %s AND election_id = %s"
            cur.execute(query, (voter_id, election_id))
            vote_count = cur.fetchone()[0]
            if vote_count > 0:
                return False
        except Exception as e:
            logging.error(f"Error checking vote status: {e}")
            return False
        finally:
            cur.close()
            conn.close()
    vote_hash = hash_vote(str(voter_id), str(candidate["candidate_id"]))
    try:
        save_vote_to_db(voter_id, candidate["candidate_id"], election_id, constituency_id, vote_hash)
        add_to_blockchain(str(voter_id), voter["voter_username"], str(candidate["candidate_id"]), candidate["candidate_name"])
        log_action("Vote Cast", f"User {voter['voter_username']} voted for {candidate['candidate_name']} in election {election['election_name']}")
        return True
    except Exception as e:
        logging.error(f"Error saving vote: {e}")
        return False

def get_vote_count_by_constituency(constituency_id: int) -> list:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            query = """
                SELECT c.candidate_name, c.party, COUNT(v.vote_id) AS vote_count
                FROM candidates c
                LEFT JOIN votes v ON c.candidate_id = v.candidate_id
                WHERE c.constituency_id = %s
                GROUP BY c.candidate_id
            """
            cur.execute(query, (constituency_id,))
            results = cur.fetchall()
            return results
        except Exception as e:
            logging.error(f"Error fetching constituency results: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def get_vote_count_by_region(region_id: int) -> list:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            query = """
                SELECT c.candidate_name, c.party, COUNT(v.vote_id) AS vote_count
                FROM candidates c
                LEFT JOIN votes v ON c.candidate_id = v.candidate_id
                INNER JOIN constituencies co ON c.constituency_id = co.constituency_id
                WHERE co.region_id = %s
                GROUP BY c.candidate_id
            """
            cur.execute(query, (region_id,))
            results = cur.fetchall()
            return results
        except Exception as e:
            logging.error(f"Error fetching region results: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def get_vote_count_by_state(state_id: int) -> list:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            query = """
                SELECT c.candidate_name, c.party, COUNT(v.vote_id) AS vote_count
                FROM candidates c
                LEFT JOIN votes v ON c.candidate_id = v.candidate_id
                INNER JOIN constituencies co ON c.constituency_id = co.constituency_id
                INNER JOIN regions r ON co.region_id = r.region_id
                WHERE r.state_id = %s
                GROUP BY c.candidate_id
            """
            cur.execute(query, (state_id,))
            results = cur.fetchall()
            return results
        except Exception as e:
            logging.error(f"Error fetching state results: {e}")
            return []
        finally:
            cur.close()
            conn.close()
    return []

def compute_vote_share(results: list) -> list:
    total_votes = sum(item["vote_count"] for item in results)
    for item in results:
        item["vote_share"] = (item["vote_count"] / total_votes * 100) if total_votes > 0 else 0
    return results

def compute_voter_turnout(results: list, total_registered: int) -> float:
    total_votes = sum(item["vote_count"] for item in results)
    turnout = (total_votes / total_registered * 100) if total_registered > 0 else 0
    return turnout

def get_winner(result_list: list) -> str:
    if not result_list:
        return "No votes cast"
    winner = max(result_list, key=lambda x: x["vote_count"])
    return f"{winner['candidate_name']} ({winner['party']}) with {winner['vote_count']} votes"

# ------------------------------------------------------------------------------
# Dynamic Dropdown Endpoints
# ------------------------------------------------------------------------------
@app.route("/get_regions")
def get_regions():
    state_id = request.args.get("state_id")
    if state_id:
        regions = fetch_regions_by_state(int(state_id))
        return jsonify(regions)
    return jsonify([])

@app.route("/get_constituencies")
def get_constituencies():
    region_id = request.args.get("region_id")
    if region_id:
        constituencies = fetch_constituencies_by_region(int(region_id))
        return jsonify(constituencies)
    return jsonify([])

@app.route("/get_candidates")
def get_candidates():
    constituency_id = request.args.get("constituency_id")
    if constituency_id:
        candidates = fetch_candidates_by_constituency(int(constituency_id))
        return jsonify(candidates)
    return jsonify([])

# ------------------------------------------------------------------------------
# Base Head for Template
# ------------------------------------------------------------------------------
base_head = """
<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
<link href="https://fonts.googleapis.com/css?family=Roboto:400,500,700&display=swap" rel="stylesheet">
<style>
  body { background: linear-gradient(135deg, #1e1e1e, #3a3a3a); font-family: 'Roboto', sans-serif; color: #ffcc00; }
  a { color: #ffcc00; }
  .btn-custom { background-color: #ffcc00; color: #000; font-weight: bold; }
  .card { background: rgba(0,0,0,0.85); border: none; border-radius: 10px; }
  .card-title { color: #ffcc00; }
  /* Floating Chat Icon */
  .floating-chat-icon {
      position: fixed;
      bottom: 30px;
      right: 30px;
      width: 60px;
      height: 60px;
      background-color: #ffcc00;
      color: #000;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.3);
      text-decoration: none;
      z-index: 1000;
  }
  .floating-chat-icon:hover {
      background-color: #e6b800;
  }
  /* Modal styles for chat history */
  .modal {
      display: none; 
      position: fixed; 
      z-index: 2000; 
      left: 0;
      top: 0;
      width: 100%;
      height: 100%;
      overflow: auto;
      background-color: rgba(0,0,0,0.8);
  }
  .modal-content {
      background-color: #fefefe;
      margin: 10% auto;
      padding: 20px;
      border: 1px solid #888;
      width: 80%;
      max-width: 600px;
      border-radius: 10px;
  }
  .close {
      color: #aaa;
      float: right;
      font-size: 28px;
      font-weight: bold;
  }
  .close:hover,
  .close:focus {
      color: black;
      text-decoration: none;
      cursor: pointer;
  }
</style>
"""

# ------------------------------------------------------------------------------
# Home Page with Floating Chatbot Icon
# ------------------------------------------------------------------------------
index_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>E-Voting System</title>
  {{ base_head|safe }}
</head>
<body>
  <div class="container text-center mt-5 animate__animated animate__fadeInDown">
    <h1>E‐Voting System</h1>
    {% with messages = get_flashed_messages(with_categories=True) %}
      {% if messages %}
        <div class="mt-3">
          {% for category, message in messages %}
            <div class="alert alert-{{ 'danger' if category=='error' else 'success' }}" role="alert">
              {{ message }}
            </div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    <div class="d-flex justify-content-center">
      <button class="btn btn-custom mr-2" onclick="window.location.href='{{ url_for('login') }}'">Login</button>
      <button class="btn btn-custom ml-2" onclick="window.location.href='{{ url_for('register') }}'">Register</button>
    </div>
  </div>
  <!-- Floating Chat Icon -->
  <a href="{{ url_for('chat') }}" class="floating-chat-icon"><i class="fas fa-comment"></i></a>
</body>
</html>
"""

@app.route("/")
def index():
    if "user" in session:
        if session.get("login_mode") == "admin":
            return redirect(url_for("admin_panel"))
        else:
            return redirect(url_for("voter_panel"))
    return render_template_string(index_html, base_head=base_head)

# ------------------------------------------------------------------------------
# Registration Page
# ------------------------------------------------------------------------------
register_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Register - E‐Voting System</title>
  {{ base_head|safe }}
</head>
<body>
  <div class="container mt-5">
    <div class="card mx-auto animate__animated animate__zoomIn" style="max-width: 500px;">
      <div class="card-body">
        <h2 class="card-title text-center mb-4">Voter Registration</h2>
        {% with messages = get_flashed_messages(with_categories=True) %}
          {% if messages %}
            <div>
              {% for category, message in messages %}
                <div class="alert alert-{{ 'danger' if category=='error' else 'success' }}" role="alert">
                  {{ message }}
                </div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}
        <form method="post">
          {% if show_register_otp %}
            <!-- OTP Verification Form -->
            <div class="form-group">
              <label>Username:</label>
              <input type="text" name="username" class="form-control" value="{{ session.get('temp_username') }}" readonly required>
            </div>
            <div class="form-group">
              <label>Voter ID (11 digits):</label>
              <input type="text" name="voter_identifier" class="form-control" value="{{ session.get('temp_voter_identifier') }}" readonly required>
            </div>
            <div class="form-group">
              <label>Email ID:</label>
              <input type="email" name="email" class="form-control" value="{{ session.get('temp_email') }}" readonly required>
            </div>
            <div class="form-group">
              <label>Enter OTP sent to your email:</label>
              <input type="text" name="register_otp" class="form-control" required>
            </div>
            <div class="form-group">
              <small id="otpCountdown" style="display: block; color: #ccc;">You can regenerate OTP in <span id="countdown">120</span> seconds.</small>
              <a href="#" id="regenerateOtpLink" class="btn btn-link" style="display:none;">Regenerate OTP</a>
            </div>
            <script>
              var countdownElement = document.getElementById('countdown');
              var regenerateLink = document.getElementById('regenerateOtpLink');
              var secondsLeft = 120;
              var timerInterval = setInterval(function() {
                  secondsLeft--;
                  countdownElement.textContent = secondsLeft;
                  if(secondsLeft <= 0) {
                      clearInterval(timerInterval);
                      document.getElementById('otpCountdown').style.display = 'none';
                      regenerateLink.style.display = 'inline';
                  }
              }, 1000);
              regenerateLink.addEventListener('click', function(e) {
                  e.preventDefault();
                  fetch('/regenerate_otp', { method: 'POST' })
                  .then(response => response.json())
                  .then(data => {
                      alert(data.message);
                      if(data.success) {
                          secondsLeft = 120;
                          regenerateLink.style.display = 'none';
                          document.getElementById('otpCountdown').style.display = 'block';
                          countdownElement.textContent = secondsLeft;
                          timerInterval = setInterval(function() {
                              secondsLeft--;
                              countdownElement.textContent = secondsLeft;
                              if(secondsLeft <= 0) {
                                  clearInterval(timerInterval);
                                  document.getElementById('otpCountdown').style.display = 'none';
                                  regenerateLink.style.display = 'inline';
                              }
                          }, 1000);
                      }
                  });
              });
            </script>
          {% else %}
            <!-- Initial Registration Form -->
            <div class="form-group">
              <label>Username:</label>
              <input type="text" name="username" class="form-control" required>
            </div>
            <div class="form-group">
              <label>Voter ID (11 digits):</label>
              <input type="text" name="voter_identifier" class="form-control" required>
            </div>
            <div class="form-group">
              <label>Email ID:</label>
              <input type="email" name="email" class="form-control" required>
            </div>
          {% endif %}
          <button type="submit" class="btn btn-custom btn-block mt-3">
            {% if show_register_otp %}Verify OTP{% else %}Register{% endif %}
          </button>
        </form>
        <p class="mt-3 text-center">Already have an account? <a href="{{ url_for('login') }}">Login here</a>.</p>
      </div>
    </div>
  </div>
</body>
</html>
"""

@app.route("/register", methods=["GET", "POST"])
def register():
    show_register_otp = False
    if request.method == "POST":
        if 'register_otp' not in request.form:
            username = request.form.get("username").strip()
            voter_identifier = request.form.get("voter_identifier").strip()
            email = request.form.get("email").strip()
            if not username or not voter_identifier or not email:
                flash("All fields are required.", "error")
            elif not is_valid_voter_id(voter_identifier):
                flash("Voter ID must be exactly 11 digits.", "error")
            elif voter_id_exists(voter_identifier):
                flash("Voter ID already exists.", "error")
            elif not re.match(r"[^@]+@[^@]+\.[a-zA-Z]{2,}", email):
                flash("Invalid email format.", "error")
            else:
                secret_key = pyotp.random_base32()
                otp = generate_otp(6)
                if send_otp_email(email, otp):
                    session['register_secret'] = secret_key
                    session['temp_username'] = username
                    session['temp_voter_identifier'] = voter_identifier
                    session['temp_email'] = email
                    session['otp'] = otp  # Store OTP in session
                    session['otp_time'] = time.time()  # Store OTP generation time
                    flash("OTP sent to your email.", "info")
                    show_register_otp = True
                else:
                    flash("Error sending OTP. Try again later.", "error")
        else:
            entered_otp = request.form.get("register_otp").strip()
            stored_otp = session.get("otp")
            if entered_otp == stored_otp:
                username = session.get('temp_username')
                voter_identifier = session.get('temp_voter_identifier')
                email = session.get('temp_email')
                if register_voter(username, voter_identifier, email, session.get('register_secret')):
                    flash(f"Voter {username} registered successfully!", "success")
                    session.pop('register_secret', None)
                    session.pop('temp_username', None)
                    session.pop('temp_voter_identifier', None)
                    session.pop('temp_email', None)
                    session.pop('otp', None)
                    return redirect(url_for('login'))
                else:
                    flash("Voter registration failed.", "error")
            else:
                flash("Invalid OTP. Registration failed.", "error")
    return render_template_string(register_html, show_register_otp=show_register_otp, base_head=base_head)

@app.route("/regenerate_otp", methods=["POST"])
def regenerate_otp():
    if 'temp_email' not in session:
        return jsonify({"success": False, "message": "Registration session expired."})
    last_time = session.get('otp_time', 0)
    current_time = time.time()
    if current_time - last_time < 120:
        remaining = int(120 - (current_time - last_time))
        return jsonify({"success": False, "message": f"Please wait {remaining} seconds before regenerating OTP."})
    otp = generate_otp(6)
    if send_otp_email(session['temp_email'], otp):
        session['otp'] = otp
        session['otp_time'] = current_time
        return jsonify({"success": True, "message": "OTP regenerated and sent to your email."})
    else:
        return jsonify({"success": False, "message": "Error sending OTP."})

# ------------------------------------------------------------------------------
# Login Page
# ------------------------------------------------------------------------------
login_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Login - E‐Voting System</title>
  {{ base_head|safe }}
</head>
<body>
  <div class="container mt-5">
    <div class="card mx-auto animate__animated animate__zoomIn" style="max-width: 500px;">
      <div class="card-body">
        <h2 class="card-title text-center mb-4">Login</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div>
              {% for category, message in messages %}
                <div class="alert alert-{{ 'danger' if category=='error' else 'success' }}" role="alert">
                  {{ message }}
                </div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}
        <form method="post">
          <div class="form-group">
            <label>Login as:</label>
            <select name="login_mode" id="login_mode-select" class="form-control">
              <option value="Voter">Voter</option>
              <option value="Admin">Admin</option>
            </select>
          </div>
          {% if show_login_otp %}
            <div class="form-group">
              <label>Username:</label>
              <input type="text" name="username" class="form-control" value="{{ prefilled_username }}" readonly required>
            </div>
            <div class="form-group">
              <label>Voter ID (11 digits):</label>
              <input type="text" name="voter_identifier" class="form-control" value="{{ prefilled_voter_identifier }}" readonly required>
            </div>
            <div class="form-group">
              <label>Enter Your Login OTP:</label>
              <input type="text" name="login_otp" class="form-control" required>
            </div>
          {% else %}
            <div class="form-group">
              <label>Username:</label>
              <input type="text" name="username" class="form-control" required>
            </div>
            <div id="voter_login_fields" class="form-group">
              <label>Voter ID (11 digits):</label>
              <input type="text" name="voter_identifier" class="form-control" required>
            </div>
          {% endif %}
          <div id="admin_login_fields" class="form-group" style="display:none;">
            <label>Password:</label>
            <input type="password" name="password" class="form-control">
          </div>
          <button type="submit" class="btn btn-custom btn-block mt-3">Login</button>
        </form>
        <p class="text-center mt-3">Don't have an account? <a href="{{ url_for('register') }}">Register Here</a></p>
      </div>
    </div>
  </div>
  <script>
    function toggleLoginFields() {
      const loginSelect = document.getElementById('login_mode-select');
      const voterLoginFields = document.getElementById('voter_login_fields');
      const adminLoginFields = document.getElementById('admin_login_fields');
      const voterInput = document.querySelector('input[name="voter_identifier"]');
      const passwordInput = document.querySelector('input[name="password"]');
      if (loginSelect.value === 'Admin') {
        voterLoginFields.style.display = 'none';
        adminLoginFields.style.display = 'block';
        if(voterInput) { voterInput.removeAttribute('required'); }
        if(passwordInput) { passwordInput.setAttribute('required', 'required'); }
      } else {
        voterLoginFields.style.display = 'block';
        adminLoginFields.style.display = 'none';
        if(voterInput) { voterInput.setAttribute('required', 'required'); }
        if(passwordInput) { passwordInput.removeAttribute('required'); }
      }
    }
    document.getElementById('login_mode-select').addEventListener('change', toggleLoginFields);
    window.onload = toggleLoginFields;
  </script>
</body>
</html>
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    show_login_otp = False
    prefilled_username = ""
    prefilled_voter_identifier = ""
    if request.method == "POST":
        login_mode = request.form.get("login_mode")
        username = request.form.get("username").strip()
        if login_mode == "Voter":
            voter_identifier = request.form.get("voter_identifier").strip()
            if 'login_otp' not in request.form:
                user_obj = login_voter(username, voter_identifier)
                if user_obj.get("otp_pending"):
                    show_login_otp = True
                    prefilled_username = user_obj.get("prefilled_username", username)
                    prefilled_voter_identifier = user_obj.get("prefilled_voter_identifier", voter_identifier)
                    return render_template_string(login_html, show_login_otp=show_login_otp,
                                                  prefilled_username=prefilled_username,
                                                  prefilled_voter_identifier=prefilled_voter_identifier,
                                                  base_head=base_head)
            else:
                login_otp = request.form.get("login_otp").strip()
                user_obj = login_voter(username, voter_identifier, otp_provided=login_otp)
                if user_obj and "otp_pending" not in user_obj:
                    session["user"] = user_obj
                    session["login_mode"] = "voter"
                    return redirect(url_for("voter_panel"))
                else:
                    flash("Invalid OTP or credentials. Please try again.", "error")
        else:
            password = request.form.get("password").strip()
            if not username or not password:
                flash("Please enter both Username and Password for admin login.", "error")
            else:
                admin_obj = login_admin(username, password)
                if admin_obj:
                    session["user"] = admin_obj
                    session["login_mode"] = "admin"
                    flash(f"Welcome back, {username}!", "success")
                    return redirect(url_for("admin_panel"))
                else:
                    flash("Invalid admin credentials. Please try again.", "error")
    return render_template_string(login_html, show_login_otp=False, base_head=base_head)

# ------------------------------------------------------------------------------
# Logout
# ------------------------------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

# ------------------------------------------------------------------------------
# Voter Panel
# ------------------------------------------------------------------------------
voter_panel_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Voter Panel - E-Voting System</title>
  {{ base_head|safe }}
</head>
<body>
  <div class="container mt-5 animate__animated animate__fadeInUp">
    <h1 class="text-center mb-4">Voter Panel</h1>
    {% with messages = get_flashed_messages(with_categories=True) %}
      {% if messages %}
        <div>
          {% for category, message in messages %}
            <div class="alert alert-{{ 'danger' if category=='error' else 'success' }}" role="alert">
              {{ message }}
            </div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    <form method="post">
      <h3>Cast Your Vote</h3>
      <div class="form-group">
        <label>Select State:</label>
        <select id="state-select" name="state" class="form-control" required>
          <option value="">-- Select State --</option>
          {% for state in states %}
            <option value="{{ state.state_id }}">{{ state.state_name }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="form-group">
        <label>Select Region:</label>
        <select id="region-select" name="region" class="form-control" required>
          <option value="">-- Select Region --</option>
        </select>
      </div>
      <div class="form-group">
        <label>Select Constituency:</label>
        <select id="constituency-select" name="constituency" class="form-control" required>
          <option value="">-- Select Constituency --</option>
        </select>
      </div>
      <div class="form-group">
        <label>Select Candidate:</label>
        <select id="candidate-select" name="candidate" class="form-control" required>
          <option value="">-- Select Candidate --</option>
        </select>
      </div>
      <button type="submit" class="btn btn-custom btn-block mt-3">Vote</button>
    </form>
    <hr>
    <h3>Your Voting History (Simulated Blockchain)</h3>
    {% if blockchain %}
      <div class="table-responsive">
      <table class="table table-dark table-striped animate__animated animate__fadeIn">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Username</th>
            <th>Candidate</th>
            <th>Vote Hash</th>
          </tr>
        </thead>
        <tbody>
          {% for block in blockchain %}
          <tr>
            <td>{{ block.timestamp }}</td>
            <td>{{ block.voter_username }}</td>
            <td>{{ block.candidate_name }}</td>
            <td>{{ block.vote_hash }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      </div>
    {% else %}
      <p>No votes recorded yet.</p>
    {% endif %}
    <p class="text-center mt-3"><a href="{{ url_for('logout') }}">Logout</a></p>
  </div>
  <script>
    document.getElementById("state-select").addEventListener("change", function() {
      var stateId = this.value;
      fetch("/get_regions?state_id=" + stateId)
        .then(response => response.json())
        .then(data => {
          var regionSelect = document.getElementById("region-select");
          regionSelect.innerHTML = '<option value="">-- Select Region --</option>';
          data.forEach(function(region) {
            var opt = document.createElement("option");
            opt.value = region.region_id;
            opt.innerHTML = region.region_name;
            regionSelect.appendChild(opt);
          });
          document.getElementById("constituency-select").innerHTML = '<option value="">-- Select Constituency --</option>';
          document.getElementById("candidate-select").innerHTML = '<option value="">-- Select Candidate --</option>';
        });
    });
    document.getElementById("region-select").addEventListener("change", function() {
      var regionId = this.value;
      fetch("/get_constituencies?region_id=" + regionId)
        .then(response => response.json())
        .then(data => {
          var constituencySelect = document.getElementById("constituency-select");
          constituencySelect.innerHTML = '<option value="">-- Select Constituency --</option>';
          data.forEach(function(constituency) {
            var opt = document.createElement("option");
            opt.value = constituency.constituency_id;
            opt.innerHTML = constituency.constituency_name;
            constituencySelect.appendChild(opt);
          });
          document.getElementById("candidate-select").innerHTML = '<option value="">-- Select Candidate --</option>';
        });
    });
    document.getElementById("constituency-select").addEventListener("change", function() {
      var constituencyId = this.value;
      fetch("/get_candidates?constituency_id=" + constituencyId)
        .then(response => response.json())
        .then(data => {
          var candidateSelect = document.getElementById("candidate-select");
          candidateSelect.innerHTML = '<option value="">-- Select Candidate --</option>';
          data.forEach(function(candidate) {
            var opt = document.createElement("option");
            opt.value = candidate.candidate_id;
            opt.innerHTML = candidate.candidate_name;
            candidateSelect.appendChild(opt);
          });
        });
    });
  </script>
</body>
</html>
"""

@app.route("/voter", methods=["GET", "POST"])
def voter_panel():
    if "user" not in session or session.get("login_mode") != "voter":
        flash("Please login as a voter to access the voter panel.", "error")
        return redirect(url_for("login"))
    if request.method == "POST":
        state_id = request.form.get("state")
        region_id = request.form.get("region")
        constituency_id = request.form.get("constituency")
        candidate_id = request.form.get("candidate")
        user = session.get("user")
        candidates = fetch_candidates_by_constituency(int(constituency_id))
        candidate_name = next((c["candidate_name"] for c in candidates if str(c["candidate_id"]) == candidate_id), "Candidate")
        candidate = {"candidate_id": candidate_id, "candidate_name": candidate_name}
        if handle_vote(user, candidate, int(constituency_id)):
            flash(f"Your vote for {candidate_name} has been recorded!", "success")
        else:
            flash("Error recording vote (perhaps you have already voted).", "error")
        return redirect(url_for("voter_panel"))
    states = fetch_states()
    current_user_id = session.get("user", {}).get("voter_id")
    user_blockchain = [block for block in blockchain if block["voter_id"] == str(current_user_id)]
    return render_template_string(voter_panel_html, states=states, blockchain=user_blockchain, base_head=base_head)

# ------------------------------------------------------------------------------
# Admin Panel
# ------------------------------------------------------------------------------
admin_panel_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Admin Panel - E‐Voting System</title>
  {{ base_head|safe }}
</head>
<body>
  <div class="container mt-5 animate__animated animate__fadeInUp">
    <h1 class="text-center mb-4">Admin Panel - Election Analysis</h1>
    {% with messages = get_flashed_messages(with_categories=True) %}
      {% if messages %}
        <div>
          {% for category, message in messages %}
            <div class="alert alert-{{ 'danger' if category=='error' else 'success' }}" role="alert">
              {{ message }}
            </div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    <form method="post">
      <div class="form-group">
        <label>View Results By:</label>
        <select name="view_level" id="view-level-select" class="form-control">
          <option value="Constituency">Constituency</option>
          <option value="Region">Region</option>
          <option value="State">State</option>
        </select>
      </div>
      <div class="form-group">
        <label>Select State:</label>
        <select id="admin-state-select" name="state" class="form-control" required>
          <option value="">-- Select State --</option>
          {% for state in states %}
            <option value="{{ state.state_id }}">{{ state.state_name }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="form-group">
        <label>Select Region:</label>
        <select id="admin-region-select" name="region" class="form-control">
          <option value="">-- Select Region --</option>
        </select>
      </div>
      <div class="form-group">
        <label>Select Constituency:</label>
        <select id="admin-constituency-select" name="constituency" class="form-control">
          <option value="">-- Select Constituency --</option>
        </select>
      </div>
      <div class="form-group">
        <label>Total Registered Voters:</label>
        <input type="number" name="total_registered" class="form-control">
      </div>
      <button type="submit" class="btn btn-custom btn-block mt-3">Get Results</button>
    </form>
    {% if results %}
      <hr>
      <div class="form-group mt-3">
        <label>Select Chart:</label>
        <select id="chart-select" name="chart_select" class="form-control">
          <option value="">-- Select Chart --</option>
          <option value="pie">Pie Chart</option>
          <option value="bar">Bar Chart</option>
          <option value="line">Line Chart</option>
        </select>
      </div>
      <div id="pie-chart-container" style="display: none;">
        <h3 class="mt-4">Pie Chart</h3>
        <div>{{ pie_chart|safe }}</div>
      </div>
      <div id="bar-chart-container" style="display: none;">
        <h3 class="mt-4">Bar Chart</h3>
        <div>{{ bar_chart|safe }}</div>
      </div>
      <div id="line-chart-container" style="display: none;">
        <h3 class="mt-4">Line Chart</h3>
        <div>{{ line_chart|safe }}</div>
      </div>
      <script>
      document.getElementById("chart-select").addEventListener("change", function() {
          var selectedChart = this.value;
          var pieContainer = document.getElementById("pie-chart-container");
          var barContainer = document.getElementById("bar-chart-container");
          var lineContainer = document.getElementById("line-chart-container");
          pieContainer.style.display = "none";
          barContainer.style.display = "none";
          lineContainer.style.display = "none";
          if (selectedChart === "pie") {
            pieContainer.style.display = "block";
          } else if (selectedChart === "bar") {
            barContainer.style.display = "block";
          } else if (selectedChart === "line") {
            lineContainer.style.display = "block";
          }
      });
      </script>
      <hr>
      <h3>Vote Counts & Vote Share</h3>
      <div class="table-responsive">
      <table class="table table-dark table-striped animate__animated animate__fadeIn">
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Party</th>
            <th>Votes</th>
            <th>Vote Share (%)</th>
          </tr>
        </thead>
        <tbody>
          {% for row in results %}
          <tr>
            <td>{{ row.candidate_name }}</td>
            <td>{{ row.party }}</td>
            <td>{{ row.vote_count }}</td>
            <td>{{ "%.2f"|format(row.vote_share) }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      </div>
      {% if turnout %}
        <p><strong>Voter Turnout:</strong> {{ "%.2f"|format(turnout) }}%</p>
      {% endif %}
      <h3 class="mt-4">Winning Candidate</h3>
      <p><strong>{{ winner_msg }}</strong></p>
    {% endif %}
    <p class="text-center mt-3"><a href="{{ url_for('logout') }}">Logout</a></p>
  </div>
  <script>
    document.getElementById("admin-state-select").addEventListener("change", function() {
      var stateId = this.value;
      fetch("/get_regions?state_id=" + stateId)
        .then(response => response.json())
        .then(data => {
          var regionSelect = document.getElementById("admin-region-select");
          regionSelect.innerHTML = '<option value="">-- Select Region --</option>';
          data.forEach(function(region) {
            var opt = document.createElement("option");
            opt.value = region.region_id;
            opt.innerHTML = region.region_name;
            regionSelect.appendChild(opt);
          });
          document.getElementById("admin-constituency-select").innerHTML = '<option value="">-- Select Constituency --</option>';
        });
    });
    document.getElementById("admin-region-select").addEventListener("change", function() {
      var regionId = this.value;
      fetch("/get_constituencies?region_id=" + regionId)
        .then(response => response.json())
        .then(data => {
          var constituencySelect = document.getElementById("admin-constituency-select");
          constituencySelect.innerHTML = '<option value="">-- Select Constituency --</option>';
          data.forEach(function(constituency) {
            var opt = document.createElement("option");
            opt.value = constituency.constituency_id;
            opt.innerHTML = constituency.constituency_name;
            constituencySelect.appendChild(opt);
          });
        });
    });
  </script>
</body>
</html>
"""

@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    if "user" not in session or session.get("login_mode") != "admin":
        flash("Please login as an admin to access the admin panel.", "error")
        return redirect(url_for("login"))
    results = None
    winner_msg = ""
    pie_chart = bar_chart = line_chart = ""
    turnout = None
    dashboard_verified = False
    dashboard_message = ""
    if request.method == "POST":
        if request.form.get("verify_dashboard"):
            dashboard_pass = request.form.get("dashboard_pass")
            if dashboard_pass and dashboard_pass == session["user"].get("Password", ""):
                dashboard_verified = True
                admin_username = session["user"].get("admin_username", "Admin")
                dashboard_message = f"Welcome, {admin_username}! You have successfully accessed the Real‐time Voting Dashboard."
            else:
                flash("Incorrect password. Dashboard access denied.", "error")
        else:
            view_level = request.form.get("view_level")
            state_id = request.form.get("state")
            region_id = request.form.get("region")
            constituency_id = request.form.get("constituency")
            if view_level == "Constituency" and constituency_id:
                results = get_vote_count_by_constituency(int(constituency_id))
                winner_msg = f"Winning Candidate: {get_winner(results)}"
            elif view_level == "Region" and region_id:
                results = get_vote_count_by_region(int(region_id))
                winner_msg = f"Winning Candidate in Region: {get_winner(results)}"
            elif view_level == "State" and state_id:
                results = get_vote_count_by_state(int(state_id))
                winner_msg = f"Winning Candidate in State: {get_winner(results)}"
            if results:
                results = compute_vote_share(results)
                df = pd.DataFrame(results)
                pie_fig = px.pie(df, values="vote_count", names="candidate_name", title="Vote Distribution", color_discrete_sequence=px.colors.qualitative.Bold)
                bar_fig = px.bar(df, x="candidate_name", y="vote_count", title="Votes per Candidate", color="candidate_name", color_discrete_sequence=px.colors.qualitative.Bold)
                line_fig = px.line(df, x="candidate_name", y="vote_count", title="Votes Trend", markers=True)
                pie_chart = pie_fig.to_html(full_html=False)
                bar_chart = bar_fig.to_html(full_html=False)
                line_chart = line_fig.to_html(full_html=False)
                total_registered = request.form.get("total_registered")
                if total_registered:
                    turnout = compute_voter_turnout(results, int(total_registered))
    states = fetch_states()
    return render_template_string(admin_panel_html,
                                  results=results,
                                  winner_msg=winner_msg,
                                  pie_chart=pie_chart,
                                  bar_chart=bar_chart,
                                  line_chart=line_chart,
                                  turnout=turnout,
                                  audit_logs=audit_logs,
                                  dashboard_verified=dashboard_verified,
                                  dashboard_message=dashboard_message,
                                  states=states,
                                  base_head=base_head)

chatbot_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Chatbot - E Voting System</title>
  {{ base_head|safe }}
  <style>
    body {
      background: linear-gradient(135deg, #1e1e1e, #3a3a3a);
      font-family: 'Roboto', sans-serif;
    }
    .chat-container {
      max-width: 700px;
      margin: 40px auto;
      background-color: #1f1f1f;
      border-radius: 15px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.3);
      padding: 20px;
    }
    .chat-header {
      text-align: center;
      margin-bottom: 20px;
      color: #ffcc00;
      font-size: 24px;
      font-weight: bold;
    }
    .chat-log {
      height: 400px;
      overflow-y: auto;
      background: #292929;
      border-radius: 10px;
      padding: 15px;
      margin-bottom: 15px;
      box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
    }
    .message {
      margin: 10px 0;
      display: flex;
      align-items: flex-start;
    }
    .message.bot {
      justify-content: flex-start;
    }
    .message.user {
      justify-content: flex-end;
    }
    .message-content {
      max-width: 80%;
      padding: 10px 15px;
      border-radius: 15px;
      font-size: 16px;
      line-height: 1.4;
    }
    .message.bot .message-content {
      background: #444;
      color: #fff;
      border-top-left-radius: 0;
    }
    .message.user .message-content {
      background: #ffcc00;
      color: #000;
      border-top-right-radius: 0;
    }
    .chat-input-container {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    .chat-input {
      flex: 1;
      padding: 12px 15px;
      border: none;
      border-radius: 25px;
      font-size: 16px;
      outline: none;
    }
    .chat-send, .chat-record, .chat-history, .chat-new {
      padding: 12px 15px;
      border: none;
      border-radius: 25px;
      background: #ffcc00;
      color: #000;
      font-size: 16px;
      font-weight: bold;
      cursor: pointer;
      transition: background 0.3s ease;
    }
    .chat-send:hover, .chat-record:hover, .chat-history:hover, .chat-new:hover {
      background: #e6b800;
    }
    /* Modal styles for chat history */
    .modal {
      display: none; 
      position: fixed; 
      z-index: 2000; 
      left: 0;
      top: 0;
      width: 100%;
      height: 100%;
      overflow: auto;
      background-color: rgba(0,0,0,0.8);
    }
    .modal-content {
      background-color: #fefefe;
      margin: 10% auto;
      padding: 20px;
      border: 1px solid #888;
      width: 80%;
      max-width: 600px;
      border-radius: 10px;
      color: #000;
    }
    .close {
      color: #aaa;
      float: right;
      font-size: 28px;
      font-weight: bold;
    }
    .close:hover,
    .close:focus {
      color: black;
      text-decoration: none;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <div class="container chat-container">
    <h2 class="chat-header">Intelligent Chatbot Assistant</h2>
    <div id="chat-log" class="chat-log"></div>
    <div class="chat-input-container">
      <input type="text" id="chat-input" class="chat-input" placeholder="Type your message here..." />
      <button id="send-btn" class="chat-send">Send</button>
      <button id="record-btn" class="chat-record"><i class="fas fa-microphone"></i></button>
    </div>
    <div class="chat-input-container" style="margin-top:10px;">
      <button id="history-btn" class="chat-history"><i class="fas fa-history"></i> History</button>
      <button id="newchat-btn" class="chat-new"><i class="fas fa-plus-circle"></i> New Chat</button>
    </div>
    <!-- Modal for chat history -->
    <div id="chat-history-modal" class="modal">
      <div class="modal-content">
        <span id="close-modal" class="close">&times;</span>
        <h3>Chat History</h3>
        <div id="chat-history-content"></div>
      </div>
    </div>
    <p class="mt-3" style="text-align:center;"><a href="{{ url_for('index') }}">Back to Home</a></p>
  </div>
  <script>
    function appendMessage(role, text) {
      var chatLog = document.getElementById("chat-log");
      var messageDiv = document.createElement("div");
      messageDiv.className = "message " + role;
      var contentDiv = document.createElement("div");
      contentDiv.className = "message-content";
      contentDiv.innerText = text;
      messageDiv.appendChild(contentDiv);
      chatLog.appendChild(messageDiv);
      chatLog.scrollTop = chatLog.scrollHeight;
    }
    document.getElementById("send-btn").addEventListener("click", function() {
      var inputField = document.getElementById("chat-input");
      var message = inputField.value;
      if (message.trim() === "") return;
      appendMessage("user", message);
      inputField.value = "";
      fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message })
      })
      .then(response => response.json())
      .then(data => {
        appendMessage("bot", data.response);
      });
    });
    document.getElementById("chat-input").addEventListener("keypress", function(e) {
      if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("send-btn").click();
      }
    });
    // Additional code for voice assistant and chat history handling goes here.
  </script>
</body>
</html>
"""

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        data = request.get_json()
        user_message = data.get("message")
        bot_response = f"You said: {user_message}"
        return jsonify({"response": bot_response})
    return render_template_string(chatbot_html, base_head=base_head)

if __name__ == "__main__":
    app.run(debug=True)