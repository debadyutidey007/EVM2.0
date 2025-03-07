try:
    import tf_keras
except ImportError as e:
    raise ImportError("tf-keras package is required for DeepFace. Please run 'pip install tf-keras' or downgrade your tensorflow version.") from e

import os
import re
import logging
import hashlib
import mysql.connector
import pandas as pd
import plotly.express as px
import pyotp
import time
import random
import secrets
import smtplib
from email.message import EmailMessage
import numpy as np
import base64
import secrets
import json
import face_recognition
from deepface import DeepFace
from email.message import EmailMessage
from io import BytesIO
from PIL import Image
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify
import openai
from werkzeug.exceptions import RequestEntityTooLarge
from flask_session import Session

# Updated threshold for normalized embeddings using DeepFace (L2 normalized)
FACE_VERIFICATION_THRESHOLD = 0.7

# Load environment variables and set up Flask
load_dotenv(".env")  
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # Allow up to 64 MB uploads
app.secret_key = 'your_secret_key_here'
app.permanent_session_lifetime = timedelta(minutes=30)  # Extend session lifetime to 30 minutes

# Use server-side session storage to ensure session persistence
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.errorhandler(RequestEntityTooLarge)
def handle_large_request(e):
    return "Uploaded data is too large. Please ensure your face scan is below 64MB.", 413

# File for chatbot conversation history
CHAT_HISTORY_FILE = "chat_history.json"

# Set Up Logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename='evoting_system.log',
                    filemode='a')

# Blockchain and audit_log simulation part 
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

def get_voter_by_id(voter_id: int) -> dict:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True, buffered=True)
            cur.execute("SELECT voter_id, voter_username, voter_identifier, face_data FROM voters WHERE voter_id = %s", (voter_id,))
            return cur.fetchone() or {}
        except Exception as e:
            logging.error(f"Error fetching voter by id: {e}")
            return {}
        finally:
            cur.close()
            conn.close()
    return {}

# # OTP Generator
# def generate_otp(length: int = 6) -> str:
#     return ''.join(str(secrets.randbelow(10)) for _ in range(length))

# # Send OTP to the users email
# #def send_otp_email(receiver_email, otp):
# #   sender_email = os.getenv("EMAIL_USER")
# #   sender_password = os.getenv("EMAIL_PASSWORD")
    
# #   msg = EmailMessage()
# #   msg["Subject"] = "Your OTP for Voter Registration"
# #   msg["From"] = sender_email
# #   msg["To"] = receiver_email
# #   msg.set_content(f"Your OTP for voter registration is: {otp}")
    
# #   try:
# #       with smtplib.SMTP("smtp.gmail.com", 587) as server:
# #           server.starttls()
# #           server.login(sender_email, sender_password)
# #           server.send_message(msg)
# #       return True
# #   except Exception as e:
# #       print(f"Email sending failed: {e}")
# #       return False

def generate_otp(length: int = 6) -> str:
    return ''.join(str(secrets.randbelow(10)) for _ in range(length))

def is_valid_email(email: str) -> tuple[bool, str]:
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    known_domains = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "aol.com", "protonmail.com"}
    
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

def get_face_encoding(face_data_str):
    """
    Given a base64 data URL of an image or a JSON array of such images,
    decode it, load it as a NumPy array, and then use DeepFace with the "Facenet" model
    to obtain a robust face embedding. The embedding is L2 normalized.
    If multiple images are provided, returns the average normalized embedding.
    """
    try:
        def compute_embedding(image_array):
            representation = DeepFace.represent(image_array, model_name="Facenet", enforce_detection=False)
            if representation and "embedding" in representation[0]:
                embedding = np.array(representation[0]["embedding"])
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    return embedding / norm
            return None

        if face_data_str.strip().startswith('['):
            face_list = json.loads(face_data_str)
            embeddings = []
            for data in face_list:
                header, encoded = data.split(',', 1)
                img_data = base64.b64decode(encoded)
                image = np.array(Image.open(BytesIO(img_data)))
                embedding = compute_embedding(image)
                if embedding is not None:
                    embeddings.append(embedding)
            if embeddings:
                avg_embedding = np.mean(embeddings, axis=0)
                norm = np.linalg.norm(avg_embedding)
                if norm > 0:
                    return avg_embedding / norm
        else:
            header, encoded = face_data_str.split(',', 1)
            img_data = base64.b64decode(encoded)
            image = np.array(Image.open(BytesIO(img_data)))
            embedding = compute_embedding(image)
            if embedding is not None:
                return embedding
    except Exception as e:
        logging.error(f"Error decoding face data: {e}")
    return None

def is_face_already_registered(new_encoding, threshold=FACE_VERIFICATION_THRESHOLD):
    """
    Check if the provided face encoding matches any of the stored face encodings in the voters table.
    Returns True if a match is found.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            query = "SELECT voter_id, face_data FROM voters WHERE face_data IS NOT NULL"
            cur.execute(query, ())
            existing_voters = cur.fetchall()
            for voter in existing_voters:
                stored_face_data = voter.get("face_data")
                if stored_face_data:
                    stored_encoding = get_face_encoding(stored_face_data)
                    if stored_encoding is not None:
                        distance = np.linalg.norm(np.array(new_encoding) - np.array(stored_encoding))
                        if distance < threshold:
                            logging.debug(f"Found matching face (distance: {distance}) for voter_id {voter['voter_id']}")
                            return True
            return False
        except Exception as e:
            logging.error(f"Error checking face registration: {e}")
            return False
        finally:
            cur.close()
            conn.close()
    return False

def ensure_face_data_column():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SHOW COLUMNS FROM voters LIKE 'face_data'")
            result = cur.fetchone()
            if not result:
                cur.execute("ALTER TABLE voters ADD COLUMN face_data MEDIUMTEXT")
                conn.commit()
                logging.debug("face_data column added to voters table as MEDIUMTEXT.")
        except Exception as e:
            logging.error(f"Error ensuring face_data column: {e}")
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

def register_voter(username: str, voter_identifier: str, email: str, secret_key: str, face_data: str = None) -> bool:
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            query = """
                INSERT INTO voters (voter_username, full_name, voter_identifier, email, otp_secret, face_data)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(query, (username, username, voter_identifier, email, secret_key, face_data))
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
    # (Validation code remains unchanged)
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True, buffered=True)
            query = """
                SELECT voter_id, voter_username, voter_identifier, otp_secret, face_data
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
                    if totp.verify(otp_provided, valid_window=2):
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

def get_voter_by_face(new_encoding, threshold=FACE_VERIFICATION_THRESHOLD):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            query = "SELECT voter_id, voter_username, face_data FROM voters WHERE face_data IS NOT NULL"
            cur.execute(query)
            voters = cur.fetchall()
            for voter in voters:
                stored_face_data = voter.get("face_data")
                if stored_face_data:
                    stored_encoding = get_face_encoding(stored_face_data)
                    if stored_encoding is not None:
                        distance = np.linalg.norm(np.array(new_encoding) - np.array(stored_encoding))
                        if distance < threshold:
                            return voter
            return None
        except Exception as e:
            logging.error(f"Error in get_voter_by_face: {e}")
            return None
        finally:
            cur.close()
            conn.close()
    return None

@app.route("/detect_face", methods=["POST"])
def detect_face():
    face_data = request.form.get("face_data")
    if not face_data:
        return jsonify({"success": False, "message": "Face data is required."})
    encoding = get_face_encoding(face_data)
    if encoding is None:
        return jsonify({"success": False, "message": "No face detected in the provided data."})
    voter = get_voter_by_face(encoding)
    if voter:
        return jsonify({"success": True, "voter_username": voter.get("voter_username")})
    else:
        return jsonify({"success": False, "message": "No matching voter found."})

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
# Base Head for Templates (including Font Awesome for icons)
# ------------------------------------------------------------------------------
base_head = """ 
<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
<link href="https://fonts.googleapis.com/css?family=Roboto:400,500,700&display=swap" rel="stylesheet">
<style>
  body 
  { 
      background: linear-gradient(135deg, #1e1e1e, #3a3a3a); 
      font-family: 'Roboto', sans-serif; 
      color: #ffcc00; 
      opacity: 1;
      transition: transform 0.8s cubic-bezier(0.23, 1, 0.32, 1), opacity 0.8s cubic-bezier(0.23, 1, 0.32, 1);
  }
  a 
  { 
    color: #ffcc00; 
  }
  .btn-custom { background-color: #ffcc00; color: #000; font-weight: bold; }
  .card 
  { 
    background: rgba(0,0,0,0.85); 
    border: none; 
    border-radius: 10px; 
  }
  .card-title 
  { 
    color: #ffcc00; 
  }
  /* Floating Chat Icon */
  .floating-chat-icon 
  {
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
      cursor: move;
  }
  .floating-chat-icon:hover 
  { 
    background-color: #e6b800; 
  }
  /* Advanced Toast Styling */
  .custom-toast 
  {
      background: linear-gradient(135deg, #ffcc00, #ffc107);
      border: none;
      border-radius: 10px;
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.6);
      color: #000;
      font-weight: bold;
  }
  .custom-toast .toast-header 
  {
      background: transparent;
      border-bottom: none;
      padding-bottom: 0;
  }
  .custom-toast .toast-body 
  {
      font-size: 1rem;
      animation: pulse 1.5s infinite;
  }
  @keyframes pulse 
  {
      0% 
      { 
        opacity: 1; 
      }
      50% 
      { 
        opacity: 0.8; 
      }
      100% { opacity: 1; }
  }
  /* Advanced Page Transition Animations */
  .advanced-fade-in 
  {
      animation: advancedFadeIn 0.8s forwards;
  }
  .advanced-fade-out 
  {
      animation: advancedFadeOut 0.8s forwards;
  }
  @keyframes advancedFadeIn 
  {
      0% 
      { 
        opacity: 0; transform: scale(0.8) translateY(20px) rotate(5deg); 
      }
      100% { opacity: 1; transform: scale(1) translateY(0) rotate(0); }
  }
  @keyframes advancedFadeOut 
  {
      0% 
      { 
        opacity: 1; transform: scale(1) translateY(0) rotate(0); 
      }
      100% 
      { 
        opacity: 0; transform: scale(0.8) translateY(-20px) rotate(-5deg); 
      }
  }
</style>
<!-- Include jQuery and Bootstrap JS for Toast functionality -->
<script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@4.5.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
  // On DOM content loaded, add advanced-fade-in class to body for entry animation
  document.addEventListener("DOMContentLoaded", function() {
      document.body.classList.add("advanced-fade-in");
  });
  // Function to handle page transition animation
  function animateTransition(callback) 
  {
      document.body.classList.remove("advanced-fade-in");
      document.body.classList.add("advanced-fade-out");
      setTimeout(callback, 800);
  }
  // Intercept clicks on all anchors and form submissions for transition effect
  document.addEventListener("DOMContentLoaded", function() {
      document.querySelectorAll("a").forEach(function(anchor) {
          anchor.addEventListener("click", function(e) {
              if(anchor.target === "_blank") return;
              e.preventDefault();
              var href = anchor.href;
              animateTransition(function() {
                  window.location = href;
              });
          });
      });
      document.querySelectorAll("form").forEach(function(form) 
      {
          form.addEventListener("submit", function(e) {
              e.preventDefault();
              animateTransition(function() {
                  form.submit();
              });
          });
      });
  });
  // Chatbot Icon Drag-and-Drop Restricted to Four Corners
  document.addEventListener("DOMContentLoaded", function() {
      const chatIcon = document.querySelector('.floating-chat-icon');
      let isDragging = false;
      let offsetX = 0;
      let offsetY = 0;
  
      chatIcon.addEventListener('mousedown', function(e) {
          isDragging = true;
          offsetX = e.clientX - chatIcon.getBoundingClientRect().left;
          offsetY = e.clientY - chatIcon.getBoundingClientRect().top;
      });
  
      document.addEventListener('mousemove', function(e) 
      {
          if (isDragging) 
          {
              chatIcon.style.position = 'fixed';
              chatIcon.style.left = (e.clientX - offsetX) + 'px';
              chatIcon.style.top = (e.clientY - offsetY) + 'px';
              // Clear any fixed corner styles
              chatIcon.style.right = 'auto';
              chatIcon.style.bottom = 'auto';
          }
      });
  
      document.addEventListener('mouseup', function(e) {
          if (isDragging) 
          {
              isDragging = false;
              const windowWidth = window.innerWidth;
              const windowHeight = window.innerHeight;
              const x = e.clientX;
              const y = e.clientY;
              let finalStyle = {};
              // Snap horizontally
              if (x < windowWidth / 2) 
              {
                  finalStyle.left = '30px';
                  finalStyle.right = 'auto';
              } 
              else 
              {
                  finalStyle.right = '30px';
                  finalStyle.left = 'auto';
              }
              // Snap vertically
              if (y < windowHeight / 2) 
              {
                  finalStyle.top = '30px';
                  finalStyle.bottom = 'auto';
              } 
              else 
              {
                  finalStyle.bottom = '30px';
                  finalStyle.top = 'auto';
              }
              Object.assign(chatIcon.style, finalStyle);
          }
      });
  });
</script>
"""

# ------------------------------------------------------------------------------
# Home Page with Floating Chatbot Icon
# ------------------------------------------------------------------------------
index_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title> E - Voting System </title>
  {{ base_head|safe }}
  <style>
    body 
    {
      background: linear-gradient(45deg, #141E30, #243B55, #141E30);
      background-size: 400% 400%;
      animation: gradientBG 15s ease infinite;
    }
    @keyframes gradientBG {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }
    /* Custom Cursor Animation using an image */
    .tricolor-follow 
    {
      position: fixed;
      pointer-events: none;
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: url('cursor.png') no-repeat center center;
      background-size: cover;
      transform: translate(-50%, -50%);
      z-index: 9999;
      opacity: 0.8;
    }
  </style>
</head>
<body>
  <div class="container text-center mt-5 animate__animated animate__fadeInDown">
    <h1> E‐Voting System</h1>
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
  <!-- Floating Chatbot Icon -->
  <a href="{{ url_for('chat') }}" class="floating-chat-icon"><i class="fas fa-comment"></i></a>
  <!-- Custom Image Cursor Script with Interactive and Leave-Window Checks -->
  <script>
    const customCursor = document.createElement('div');
    customCursor.className = 'tricolor-follow';
    document.body.appendChild(customCursor);
    
    document.addEventListener('mousemove', function(e) {
      const interactiveTags = ['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'];
      if (interactiveTags.includes(e.target.tagName) || (e.target.closest && e.target.closest('.floating-chat-icon')))
        customCursor.style.display = 'none';
      else 
      {
        customCursor.style.display = 'block';
        customCursor.style.left = e.clientX + 'px';
        customCursor.style.top = e.clientY + 'px';
      }
    });
    
    window.addEventListener('mouseout', function(e) {
      if (e.clientX <= 0 || e.clientY <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight)
        customCursor.style.display = 'none';
    });
  </script>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# Home Page Route
# ------------------------------------------------------------------------------
@app.route("/")
def index():
    if "user" in session:
        if session.get("login_mode") == "admin":
            return redirect(url_for("admin_panel"))
        else:
            return redirect(url_for("voter_panel"))
    return render_template_string(index_html, base_head=base_head)

face_register_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Face Registration - E‐Voting System</title>
  {{ base_head|safe }}
  <style>
    #videoElement 
    { 
      width: 100%; 
      max-width: 400px; 
      border: 2px solid #ffcc00; 
      border-radius: 10px; 
    }
    /* Ensure the container is relative so the overlay canvas can position over video */
    .video-container 
    {
      position: relative;
      display: inline-block;
    }
    #overlay 
    {
      position: absolute;
      top: 0;
      left: 0;
      pointer-events: none;
    }
  </style>
</head>
<body>
  <div class="container mt-5">
    <div class="card mx-auto" style="max-width: 500px;">
      <div class="card-body">
        <h2 class="card-title text-center mb-4">Face Registration</h2>
        <p class="text-center">Please scan your face using your webcam.</p>
        <div class="video-container">
          <video autoplay="true" id="videoElement"></video>
          <canvas id="overlay"></canvas>
        </div>
        <canvas id="canvas" style="display:none;"></canvas>
        <form method="post" id="faceForm">
          <input type="hidden" name="face_data" id="face_data">
          <button type="button" class="btn btn-custom btn-block mt-3" id="captureBtn">Capture Single Frame</button>
          <button type="button" class="btn btn-custom btn-block mt-3" id="advancedCaptureBtn">Advanced Capture (Multiple Frames)</button>
          <button type="submit" class="btn btn-custom btn-block mt-3">Submit Registration</button>
        </form>
      </div>
    </div>
  </div>
  <!-- Advanced Toast Notification Container -->
  <div aria-live="polite" aria-atomic="true" style="position: fixed; top: 20px; right: 20px; z-index: 1080;">
    <div id="toastNotification" class="toast custom-toast animate__animated" data-delay="5000">
      <div class="toast-header">
        <strong class="mr-auto">Notification</strong>
        <small class="text-muted">now</small>
        <button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Close">
          <span aria-hidden="true">&times;</span>
        </button>
      </div>
      <div class="toast-body">
        Advanced face capture completed. You can now submit the registration.
      </div>
    </div>
  </div>
  <!-- Include face-api.js for live face detection -->
  <script defer src="https://cdn.jsdelivr.net/npm/face-api.js"></script>
  <script defer>
    Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri('/models')
    ]).then(startVideo);
    function startVideo() 
    {
      const video = document.getElementById('videoElement');
      video.addEventListener('play', () => {
        const canvas = document.getElementById('overlay');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const displaySize = { width: video.videoWidth, height: video.videoHeight };
        setInterval(async () => {
          const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions());
          const resizedDetections = faceapi.resizeResults(detections, displaySize);
          const context = canvas.getContext('2d');
          context.clearRect(0, 0, canvas.width, canvas.height);
          resizedDetections.forEach(detection => {
            const box = detection.box;
            context.strokeStyle = "#00FF00";
            context.lineWidth = 2;
            context.strokeRect(box.x, box.y, box.width, box.height);
          });
        }, 100);
      });
    }
  </script>
  <script>
    var video = document.getElementById('videoElement');
    var canvas = document.getElementById('canvas');
    var captureBtn = document.getElementById('captureBtn');
    var advancedCaptureBtn = document.getElementById('advancedCaptureBtn');
    var faceDataInput = document.getElementById('face_data');

    if (navigator.mediaDevices.getUserMedia) 
    {
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(function(stream) 
            { 
                video.srcObject = stream; 
            })
            .catch(function(error) 
            { 
                console.log("Error accessing webcam."); 
            });
    }

    captureBtn.addEventListener('click', function() {
        var desiredWidth = 320, desiredHeight = 240;
        canvas.width = desiredWidth;
        canvas.height = desiredHeight;
        canvas.getContext('2d').drawImage(video, 0, 0, desiredWidth, desiredHeight);
        var dataURL = canvas.toDataURL('image/jpeg', 0.7);
        faceDataInput.value = dataURL;
        var toastElem = $('#toastNotification');
        toastElem.find('.toast-body').text("Face captured. You can now submit the registration.");
        toastElem.removeClass('animate__fadeOutRight').addClass('animate__fadeInRight');
        toastElem.toast('show');
    });

    advancedCaptureBtn.addEventListener('click', function() {
        var desiredWidth = 320, desiredHeight = 240, frames = [], captureCount = 3, interval = 1000;
        function captureFrame(count) 
        {
            canvas.width = desiredWidth;
            canvas.height = desiredHeight;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, desiredWidth, desiredHeight);
            var dataURL = canvas.toDataURL('image/jpeg', 0.7);
            frames.push(dataURL);
            if (count < captureCount) 
            {
                setTimeout(function() { captureFrame(count + 1); }, interval);
            } 
            else 
            {
                faceDataInput.value = JSON.stringify(frames);
                var toastElem = $('#toastNotification');
                toastElem.removeClass('animate__fadeOutRight').addClass('animate__fadeInRight');
                toastElem.toast('show');
            }
        }
        captureFrame(1);
    });
  </script>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# Routes for Registration, Login, and Face Verification
# ------------------------------------------------------------------------------
@app.route("/face_register", methods=["GET", "POST"])
def face_register():
    if not all(k in session for k in ['temp_username', 'temp_voter_identifier', 'temp_email', 'register_secret']):
        flash("Registration session expired. Please register again.", "error")
        return redirect(url_for('register'))
    if request.method == "POST":
        face_data = request.form.get("face_data")
        if not face_data:
            flash("Face scan data is required.", "error")
            return render_template_string(face_register_html, base_head=base_head)
        new_encoding = get_face_encoding(face_data)
        if new_encoding is None:
            flash("No face detected. Please try again.", "error")
            return render_template_string(face_register_html, base_head=base_head)
        if is_face_already_registered(new_encoding):
            flash("This face is already registered with another account.", "error")
            return redirect(url_for('register'))
        username = session.get('temp_username')
        voter_identifier = session.get('temp_voter_identifier')
        email = session.get('temp_email')
        secret_key = session.get('register_secret')
        if register_voter(username, voter_identifier, email, secret_key, face_data):
            flash(f"Voter {username} registered successfully!", "success")
            session.pop('register_secret', None)
            session.pop('temp_username', None)
            session.pop('temp_voter_identifier', None)
            session.pop('temp_email', None)
            session.pop('otp', None)
            return redirect(url_for('login'))
        else:
            flash("Voter registration failed.", "error")
    return render_template_string(face_register_html, base_head=base_head)

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
  <style>
    body 
    {
      background: linear-gradient(45deg, #141E30, #243B55, #141E30);
      background-size: 400% 400%;
      animation: gradientBG 15s ease infinite;
    }
    @keyframes gradientBG {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }
    /* Custom Cursor Animation using an image */
    .tricolor-follow 
    {
      position: fixed;
      pointer-events: none;
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: url('cursor.png') no-repeat center center;
      background-size: cover;
      transform: translate(-50%, -50%);
      z-index: 9999;
      opacity: 0.8;
    }
  </style>
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
                  if(secondsLeft <= 0) 
                  {
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
                      if(data.success) 
                      {
                          secondsLeft = 120;
                          regenerateLink.style.display = 'none';
                          document.getElementById('otpCountdown').style.display = 'block';
                          countdownElement.textContent = secondsLeft;
                          timerInterval = setInterval(function() 
                          {
                              secondsLeft--;
                              countdownElement.textContent = secondsLeft;
                              if(secondsLeft <= 0) 
                              {
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
  <!-- Custom Image Cursor Script with Interactive and Leave-Window Checks -->
  <script>
    const customCursor = document.createElement('div');
    customCursor.className = 'tricolor-follow';
    document.body.appendChild(customCursor);
    document.addEventListener('mousemove', function(e) 
    {
      const interactiveTags = ['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'];
      if (interactiveTags.includes(e.target.tagName)) 
      {
        customCursor.style.display = 'none';
      } 
      else 
      {
        customCursor.style.display = 'block';
        customCursor.style.left = e.clientX + 'px';
        customCursor.style.top = e.clientY + 'px';
      }
    });
    window.addEventListener('mouseout', function(e) {
      if (e.clientX <= 0 || e.clientY <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight) 
      {
        customCursor.style.display = 'none';
      }
    });
  </script>
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
            # ... (existing validation code)
            secret_key = pyotp.random_base32()
            otp = generate_otp(6)
            if send_otp_email(email, otp):
                session['register_secret'] = secret_key
                session['temp_username'] = username
                session['temp_voter_identifier'] = voter_identifier
                session['temp_email'] = email
                session['otp'] = otp
                session['otp_time'] = time.time()
                flash("OTP sent to your email.", "info")
                show_register_otp = True
            else:
                flash("Error sending OTP. Try again later.", "error")
        else:
            entered_otp = request.form.get("register_otp").strip()
            stored_otp = session.get("otp")
            if entered_otp == stored_otp:
                flash("OTP verified. Please complete face registration.", "info")
                return redirect(url_for('face_register'))
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
face_login_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Face Verification - E‐Voting System</title>
  {{ base_head|safe }}
  <style>
    #videoElement 
    { 
      width: 100%; 
      max-width: 400px; 
      border: 2px solid #ffcc00; 
      border-radius: 10px; 
    }
    .video-container 
    {
      position: relative;
      display: inline-block;
    }
    #overlay 
    {
      position: absolute;
      top: 0;
      left: 0;
      pointer-events: none;
    }
  </style>
</head>
<body>
  <div class="container mt-5">
    <div class="card mx-auto" style="max-width: 500px;">
      <div class="card-body">
        <h2 class="card-title text-center mb-4">Face Verification</h2>
        <p class="text-center">Please verify your face using your webcam to complete login.</p>
        <div class="video-container">
          <video autoplay="true" id="videoElement"></video>
          <canvas id="overlay"></canvas>
        </div>
        <canvas id="canvas" style="display:none;"></canvas>
        <form method="post" id="faceForm">
          <input type="hidden" name="face_data" id="face_data">
          <button type="button" class="btn btn-custom btn-block mt-3" id="captureBtn">Capture Single Frame</button>
          <button type="button" class="btn btn-custom btn-block mt-3" id="advancedCaptureBtn">Advanced Capture (Multiple Frames)</button>
          <button type="submit" class="btn btn-custom btn-block mt-3">Verify and Login</button>
        </form>
        <!-- New Identify Me functionality -->
        <button type="button" class="btn btn-info btn-block mt-3" id="identifyBtn">Identify Me</button>
        <div id="identityResult" style="text-align: center; margin-top: 10px; color: #ffcc00;"></div>
      </div>
    </div>
  </div>
  <!-- Include face-api.js for live face detection -->
  <script defer src="https://cdn.jsdelivr.net/npm/face-api.js"></script>
  <script defer>
    Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri('/models')
    ]).then(startVideo);
    function startVideo() 
    {
      const video = document.getElementById('videoElement');
      video.addEventListener('play', () => {
        const canvas = document.getElementById('overlay');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const displaySize = { width: video.videoWidth, height: video.videoHeight };
        setInterval(async () => {
          const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions());
          const resizedDetections = faceapi.resizeResults(detections, displaySize);
          const context = canvas.getContext('2d');
          context.clearRect(0, 0, canvas.width, canvas.height);
          resizedDetections.forEach(detection => {
            const box = detection.box;
            context.strokeStyle = "#00FF00";
            context.lineWidth = 2;
            context.strokeRect(box.x, box.y, box.width, box.height);
          });
        }, 100);
      });
    }
  </script>
  <script>
    var video = document.getElementById('videoElement');
    var canvas = document.getElementById('canvas');
    var captureBtn = document.getElementById('captureBtn');
    var advancedCaptureBtn = document.getElementById('advancedCaptureBtn');
    var faceDataInput = document.getElementById('face_data');

    if (navigator.mediaDevices.getUserMedia) 
    {
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(function(stream) 
            { 
                video.srcObject = stream; 
            })
            .catch(function(error) 
            { 
                console.log("Error accessing webcam for face verification:", error); 
            });
    }

    captureBtn.addEventListener('click', function() 
    {
        var desiredWidth = 320, desiredHeight = 240;
        canvas.width = desiredWidth;
        canvas.height = desiredHeight;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, desiredWidth, desiredHeight);
        var dataURL = canvas.toDataURL('image/jpeg', 0.5);
        faceDataInput.value = dataURL;
        var toastElem = $('#toastNotification');
        toastElem.find('.toast-body').text("Face captured. You can now verify and login.");
        toastElem.removeClass('animate__fadeOutRight').addClass('animate__fadeInRight');
        toastElem.toast('show');
    });

    advancedCaptureBtn.addEventListener('click', function() 
    {
        var desiredWidth = 320, desiredHeight = 240, frames = [], captureCount = 3, interval = 1000;
        function captureFrame(count) 
        {
            canvas.width = desiredWidth;
            canvas.height = desiredHeight;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, desiredWidth, desiredHeight);
            var dataURL = canvas.toDataURL('image/jpeg', 0.5);
            frames.push(dataURL);
            if (count < captureCount) 
            {
                setTimeout(function() { captureFrame(count + 1); }, interval);
            } 
            else 
            {
                faceDataInput.value = JSON.stringify(frames);
                var toastElem = $('#toastNotification');
                toastElem.removeClass('animate__fadeOutRight').addClass('animate__fadeInRight');
                toastElem.toast('show');
            }
        }
        captureFrame(1);
    });

    // Updated Identify Me functionality with toast notifications
    document.getElementById('identifyBtn').addEventListener('click', function() 
    {
      var faceData = faceDataInput.value;
      if (!faceData) 
      {
        // Show toast notification if no face has been captured
        var toastElem = $('#toastNotification');
        toastElem.find('.toast-body').text("Please capture your face first.");
        toastElem.removeClass('animate__fadeOutRight').addClass('animate__fadeInRight');
        toastElem.toast('show');
        return;
      }
      fetch('/detect_face', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'face_data=' + encodeURIComponent(faceData)
      })
      .then(response => response.json())
      .then(data => {
        if(data.success) 
        {
          document.getElementById('identityResult').textContent = "Identified as: " + data.voter_username;
          var toastElem = $('#toastNotification');
          toastElem.find('.toast-body').text("Identified as: " + data.voter_username);
          toastElem.removeClass('animate__fadeOutRight').addClass('animate__fadeInRight');
          toastElem.toast('show');
        } 
        else 
        {
          document.getElementById('identityResult').textContent = data.message;
          var toastElem = $('#toastNotification');
          toastElem.find('.toast-body').text(data.message);
          toastElem.removeClass('animate__fadeOutRight').addClass('animate__fadeInRight');
          toastElem.toast('show');
        }
      });
    });
  </script>
  <!-- Advanced Toast Notification Container (can be shared with registration page) -->
  <div aria-live="polite" aria-atomic="true" style="position: fixed; top: 20px; right: 20px; z-index: 1080;">
    <div id="toastNotification" class="toast custom-toast animate__animated" data-delay="5000">
      <div class="toast-header">
        <strong class="mr-auto">Notification</strong>
        <small class="text-muted">now</small>
        <button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Close">
          <span aria-hidden="true">&times;</span>
        </button>
      </div>
      <div class="toast-body">
        Advanced face capture completed. You can now verify and login.
      </div>
    </div>
  </div>
</body>
</html>
"""
    
login_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Login - E‐Voting System</title>
  {{ base_head|safe }}
  <style>
    body 
    {
      background: linear-gradient(45deg, #141E30, #243B55, #141E30);
      background-size: 400% 400%;
      animation: gradientBG 15s ease infinite;
    }
    @keyframes gradientBG 
    {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }
    /* Custom Cursor Animation using an image */
    .tricolor-follow 
    {
      position: fixed;
      pointer-events: none;
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: url('cursor.png') no-repeat center center;
      background-size: cover;
      transform: translate(-50%, -50%);
      z-index: 9999;
      opacity: 0.8;
    }
  </style>
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
  <!-- Custom Image Cursor Script with Interactive and Leave-Window Checks -->
  <script>
    const customCursor = document.createElement('div');
    customCursor.className = 'tricolor-follow';
    document.body.appendChild(customCursor);
    document.addEventListener('mousemove', function(e) 
    {
      const interactiveTags = ['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'];
      if (interactiveTags.includes(e.target.tagName)) 
      {
        customCursor.style.display = 'none';
      } 
      else 
      {
        customCursor.style.display = 'block';
        customCursor.style.left = e.clientX + 'px';
        customCursor.style.top = e.clientY + 'px';
      }
    });
    window.addEventListener('mouseout', function(e) 
    {
      if (e.clientX <= 0 || e.clientY <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight) 
      {
        customCursor.style.display = 'none';
      }
    });
  </script>
  <script>
    function toggleLoginFields() 
    {
      const loginSelect = document.getElementById('login_mode-select');
      const voterLoginFields = document.getElementById('voter_login_fields');
      const adminLoginFields = document.getElementById('admin_login_fields');
      const voterInput = document.querySelector('input[name="voter_identifier"]');
      const passwordInput = document.querySelector('input[name="password"]');
      if (loginSelect.value === 'Admin') 
      {
        voterLoginFields.style.display = 'none';
        adminLoginFields.style.display = 'block';
        if(voterInput) { voterInput.removeAttribute('required'); }
        if(passwordInput) { passwordInput.setAttribute('required', 'required'); }
      } 
      else 
      {
        voterLoginFields.style.display = 'block';
        adminLoginFields.style.display = 'none';
        if(voterInput) 
        { 
          voterInput.setAttribute('required', 'required'); 
        }
        if(passwordInput) 
        { 
          passwordInput.removeAttribute('required'); 
        }
      }
    }
    document.getElementById('login_mode-select').addEventListener('change', toggleLoginFields);
    window.onload = toggleLoginFields;
  </script>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# Login Route
# ------------------------------------------------------------------------------
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
                    return render_template_string(
                        login_html,
                        show_login_otp=show_login_otp,
                        prefilled_username=prefilled_username,
                        prefilled_voter_identifier=prefilled_voter_identifier,
                        base_head=base_head
                    )
            else:
                login_otp = request.form.get("login_otp").strip()
                user_obj = login_voter(username, voter_identifier, otp_provided=login_otp)
                if user_obj and not user_obj.get("otp_pending"):
                    # Store minimal user data in session (JSON-serializable)
                    session["temp_user"] = {
                        "voter_id": user_obj["voter_id"],
                        "voter_username": user_obj["voter_username"],
                        "voter_identifier": user_obj["voter_identifier"],
                        "face_data": user_obj["face_data"],
                        "otp_secret": user_obj["otp_secret"]
                    }
                    # Mark the session as permanent and modified so it is saved
                    session.permanent = True
                    session.modified = True
                    flash("OTP verified. Please complete face verification.", "info")
                    return redirect(url_for("face_verify"))
                else:
                    flash("Invalid OTP or login failed.", "error")
        else:
            password = request.form.get("password").strip()
            admin_obj = login_admin(username, password)
            if admin_obj:
                session["user"] = admin_obj
                session["login_mode"] = "admin"
                flash("Admin logged in successfully.", "success")
                return redirect(url_for("admin_panel"))
            else:
                flash("Admin login failed.", "error")
    return render_template_string(
        login_html,
        show_login_otp=show_login_otp,
        prefilled_username=prefilled_username,
        prefilled_voter_identifier=prefilled_voter_identifier,
        base_head=base_head
    )

@app.route("/face_verify", methods=["GET", "POST"])
def face_verify():
    temp_user = session.get("temp_user")
    app.logger.debug("Session keys in face_verify: %s", list(session.keys()))
    if not temp_user:
        flash("Session expired. Please login again.", "error")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        face_data = request.form.get("face_data")
        if not face_data:
            flash("Face data is required for verification.", "error")
            return render_template_string(face_login_html, base_head=base_head)
        
        captured_encoding = get_face_encoding(face_data)
        if captured_encoding is None:
            flash("No face detected in verification. Please try again.", "error")
            return render_template_string(face_login_html, base_head=base_head)
        
        registered_face_data = temp_user.get("face_data")
        registered_encoding = get_face_encoding(registered_face_data)
        if registered_encoding is None:
            flash("Registered face data missing. Please re-register.", "error")
            return redirect(url_for("register"))
        
        distance = np.linalg.norm(np.array(captured_encoding) - np.array(registered_encoding))
        if distance < FACE_VERIFICATION_THRESHOLD:
            # Set the user as logged in and explicitly mark login_mode as "voter"
            session["user"] = temp_user
            session["login_mode"] = "voter"
            session.pop("temp_user", None)
            flash("Face verified. Logged in successfully.", "success")
            return redirect(url_for("voter_panel"))
        else:
            flash("Face verification failed. Please try again.", "error")
            return render_template_string(face_login_html, base_head=base_head)
    
    return render_template_string(face_login_html, base_head=base_head)

@app.route("/face_login_voter", methods=["GET", "POST"])
def face_login_voter():
    user_id = session.get("temp_user_id")
    if not user_id:
        flash("Session expired. Please login again.", "error")
        return redirect(url_for('login'))
    user_obj = get_voter_by_id(user_id)
    if not user_obj:
        flash("User not found. Please login again.", "error")
        return redirect(url_for('login'))
    if request.method == "POST":
        face_data = request.form.get("face_data")
        if not face_data:
            flash("Face scan data is required for login.", "error")
            return render_template_string(face_login_html, base_head=base_head)
        login_encoding = get_face_encoding(face_data)
        if login_encoding is None:
            flash("No face detected during login. Please try again.", "error")
            return render_template_string(face_login_html, base_head=base_head)
        stored_face_data = user_obj.get("face_data")
        if not stored_face_data:
            flash("No registered face data found for this account. Please complete face registration.", "error")
            return redirect(url_for('face_register'))
        stored_encoding = get_face_encoding(stored_face_data)
        if stored_encoding is None:
            flash("Error processing stored face data.", "error")
            return redirect(url_for('face_register'))
        distance = np.linalg.norm(np.array(login_encoding) - np.array(stored_encoding))
        if distance > FACE_VERIFICATION_THRESHOLD:
            flash("Face verification failed. Face does not match our records.", "error")
            return render_template_string(face_login_html, base_head=base_head)
        session["user"] = {
            "voter_id": user_obj["voter_id"],
            "voter_username": user_obj["voter_username"],
            "voter_identifier": user_obj["voter_identifier"]
        }
        session["login_mode"] = "voter"
        session.pop("temp_user_id", None)
        flash("Login Using FACE ID successful.", "info")
        flash(f"Login successful! Welcome {user_obj['voter_username']}.", "success")
        return redirect(url_for('voter_panel'))
    return render_template_string(face_login_html, base_head=base_head)

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
  <title>Voter Panel - E ‐ Voting System</title>
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
    document.getElementById("state-select").addEventListener("change", function() 
    {
      var stateId = this.value;
      fetch("/get_regions?state_id=" + stateId)
        .then(response => response.json())
        .then(data => {
          var regionSelect = document.getElementById("region-select");
          regionSelect.innerHTML = '<option value="">-- Select Region --</option>';
          data.forEach(function(region) 
          {
            var opt = document.createElement("option");
            opt.value = region.region_id;
            opt.innerHTML = region.region_name;
            regionSelect.appendChild(opt);
          });
          document.getElementById("constituency-select").innerHTML = '<option value="">-- Select Constituency --</option>';
          document.getElementById("candidate-select").innerHTML = '<option value="">-- Select Candidate --</option>';
        });
    });
    document.getElementById("region-select").addEventListener("change", function() 
    {
      var regionId = this.value;
      fetch("/get_constituencies?region_id=" + regionId)
        .then(response => response.json())
        .then(data => {
          var constituencySelect = document.getElementById("constituency-select");
          constituencySelect.innerHTML = '<option value="">-- Select Constituency --</option>';
          data.forEach(function(constituency) 
          {
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
    {% with messages = get_flashed_messages (with_categories=True) %}
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
      document.getElementById("chart-select").addEventListener("change", function() 
      {
          var selectedChart = this.value;
          var pieContainer = document.getElementById("pie-chart-container");
          var barContainer = document.getElementById("bar-chart-container");
          var lineContainer = document.getElementById("line-chart-container");
          pieContainer.style.display = "none";
          barContainer.style.display = "none";
          lineContainer.style.display = "none";
          if (selectedChart === "pie") 
          {
            pieContainer.style.display = "block";
          } 
          else if (selectedChart === "bar") 
          {
            barContainer.style.display = "block";
          } 
          else if (selectedChart === "line") 
          {
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
    document.getElementById("admin-state-select").addEventListener("change", function() 
    {
      var stateId = this.value;
      fetch("/get_regions?state_id=" + stateId)
        .then(response => response.json())
        .then(data => {
          var regionSelect = document.getElementById("admin-region-select");
          regionSelect.innerHTML = '<option value="">-- Select Region --</option>';
          data.forEach(function(region) 
          {
            var opt = document.createElement("option");
            opt.value = region.region_id;
            opt.innerHTML = region.region_name;
            regionSelect.appendChild(opt);
          });
          document.getElementById("admin-constituency-select").innerHTML = '<option value="">-- Select Constituency --</option>';
        });
    });
    document.getElementById("admin-region-select").addEventListener("change", function() 
    {
      var regionId = this.value;
      fetch("/get_constituencies?region_id=" + regionId)
        .then(response => response.json())
        .then(data => {
          var constituencySelect = document.getElementById("admin-constituency-select");
          constituencySelect.innerHTML = '<option value="">-- Select Constituency --</option>';
          data.forEach(function(constituency) 
          {
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

# ------------------------------------------------------------------------------
# Chatbot
# ------------------------------------------------------------------------------
chatbot_html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Chatbot Assistant</title>
  {{ base_head|safe }}
  <!-- Include Bootstrap CSS if not already present -->
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
  <style>
    /* Global Styles */
    body 
    {
      background: linear-gradient(135deg, #1e1e1e, #3a3a3a);
      font-family: 'Roboto', sans-serif;
      margin: 0;
      padding: 0;
      color: #eaeaea;
    }
    /* Chat Container */
    .chat-container 
    {
      max-width: 700px;
      margin: 40px auto;
      background-color: #1f1f1f;
      border-radius: 15px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.3);
      padding: 20px;
    }
    .chat-header 
    {
      font-size: 24px;
      margin-bottom: 15px;
      text-align: center;
    }
    .chat-log 
    {
      max-height: 300px;
      overflow-y: auto;
      margin-bottom: 15px;
      background: #121212;
      padding: 10px;
      border-radius: 8px;
    }
    .message 
    {
      margin-bottom: 10px;
    }
    .message.user .message-content 
    {
      background: #ffcc00;
      color: #000;
      padding: 8px 12px;
      border-radius: 8px;
      display: inline-block;
    }
    .message.bot .message-content 
    {
      background: #444;
      padding: 8px 12px;
      border-radius: 8px;
      display: inline-block;
    }
    .chat-input-container 
    {
      display: flex;
      gap: 10px;
    }
    .chat-input 
    {
      flex: 1;
      padding: 10px;
      border-radius: 5px;
      border: 1px solid #ccc;
    }
    .chat-send, .chat-record, .chat-history, .chat-new 
    {
      padding: 10px 15px;
      border: none;
      border-radius: 5px;
      background: #e94560;
      color: #fff;
      cursor: pointer;
      transition: background 0.3s ease;
    }
    .chat-send:hover, .chat-record:hover, .chat-history:hover, .chat-new:hover 
    {
      background: #d73750;
    }
  </style>
</head>
<body>
  <div class="chat-container">
    <div class="chat-header">Government Chatbot Assistant</div>
    <div id="chat-log" class="chat-log"></div>
    <div class="chat-input-container">
      <input type="text" id="chat-input" class="chat-input" placeholder="Type your message here..." />
      <button id="send-btn" class="chat-send">Send</button>
      <button id="record-btn" class="chat-record"><i class="fas fa-microphone"></i></button>
    </div>
    <div class="chat-input-container" style="justify-content: flex-end; margin-top: 10px;">
      <button id="history-btn" class="chat-history"><i class="fas fa-history"></i> History</button>
      <button id="newchat-btn" class="chat-new"><i class="fas fa-plus-circle"></i> New Chat</button>
    </div>
  </div>

  <!-- Updated Chat History Modal (Professional UI) -->
  <div id="chat-history-modal" class="modal fade" tabindex="-1" role="dialog" aria-labelledby="chatHistoryModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered" role="document">
      <div class="modal-content" style="background-color: #f8f9fa; border-radius: 10px;">
        <div class="modal-header" style="border-bottom: none;">
          <h5 class="modal-title" id="chatHistoryModalLabel" style="color: #343a40;">Chat History</h5>
          <button type="button" class="close" data-dismiss="modal" aria-label="Close" style="color: #343a40;">
            <span aria-hidden="true">&times;</span>
          </button>
        </div>
        <div class="modal-body" style="max-height: 300px; overflow-y: auto; color: #495057;">
          <div id="chat-history-content"></div>
        </div>
        <div class="modal-footer" style="border-top: none;">
          <button id="clear-history-btn" class="btn btn-danger">Clear History</button>
          <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
        </div>
      </div>
    </div>
  </div>

  <p style="text-align:center; margin: 20px 0;">
    <a href="{{ url_for('index') }}" style="color: #e94560; text-decoration: none;">Back to Home</a>
  </p>

  <!-- Include jQuery and Bootstrap JS if not already included -->
  <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.5.2/dist/js/bootstrap.bundle.min.js"></script>
  <script>
    function appendMessage(role, text) 
    {
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
    document.getElementById("send-btn").addEventListener("click", function() 
    {
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
      if (e.key === "Enter") 
      {
        e.preventDefault();
        document.getElementById("send-btn").click();
      }
    });
    // Voice Assistant Integration using Web Speech API
    var recordBtn = document.getElementById("record-btn");
    var recognition;
    if ('SpeechRecognition' in window) {
      recognition = new SpeechRecognition();
    } 
    else if ('webkitSpeechRecognition' in window) 
    {
      recognition = new webkitSpeechRecognition();
    } 
    else 
    {
      recordBtn.disabled = true;
      recordBtn.innerText = "Voice Not Supported";
    }
    if (recognition) 
    {
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';
      recordBtn.addEventListener("click", function() {
        recognition.start();
      });
      recognition.onresult = function(event) 
      {
        var transcript = event.results[0][0].transcript;
        document.getElementById("chat-input").value = transcript;
      };
      recognition.onerror = function(event) {
        console.error("Speech recognition error", event.error);
      };
    }
    // Updated Chat History Modal using Bootstrap
    document.getElementById("history-btn").addEventListener("click", function() {
      fetch("/chat_history")
      .then(response => response.json())
      .then(data => {
        var historyHtml = "";
        data.forEach(function(item) {
          historyHtml += "<p style='margin-bottom: 8px;'><strong>" + item.role.toUpperCase() + ":</strong> " 
                        + item.message + " <small class='text-muted'>(" + new Date(item.timestamp).toLocaleString() + ")</small></p>";
        });
        document.getElementById("chat-history-content").innerHTML = historyHtml;
        $('#chat-history-modal').modal('show');
      });
    });
    // New Chat Button: Clear the chat log
    document.getElementById("newchat-btn").addEventListener("click", function() {
      document.getElementById("chat-log").innerHTML = "";
    });
    // Clear History Button: Send request to clear chat history
    document.getElementById("clear-history-btn").addEventListener("click", function() {
      fetch("/clear_chat_history", { method: "POST" })
        .then(response => response.json())
        .then(data => {
          if(data.success) {
            document.getElementById("chat-history-content").innerHTML = "<p>Chat history cleared.</p>";
          } else {
            alert("Failed to clear chat history.");
          }
        });
    });
  </script>
</body>
</html>
"""

def get_chatbot_response(message: str) -> str:
    lower_message = message.lower()
    try:
        response = openai.ChatCompletion.create(
           model="gpt-3.5-turbo",
           messages=[
               {"role": "system", "content": "You are a highly intelligent assistant for an e-voting system. Provide concise and helpful answers."},
               {"role": "user", "content": message}
           ],
           temperature=0.7,
           max_tokens=150
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        # Fallback responses
        if "hi" in lower_message:
            return "Hi, how can I help you today?"
        elif "vote" in lower_message:
            return "To cast your vote, please go to the voter panel after logging in."
        elif "register" in lower_message:
            return "You can register by clicking on the Register link on the home page."
        elif "results" in lower_message:
            return "Election results can be viewed on the admin panel (login as admin required)."
        else:
            return "I'm sorry, I didn't understand that. Can you please rephrase?"

def log_chat_message(role: str, message: str):
    """Log chat messages to a JSON file."""
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, "r") as f:
                history = json.load(f)
        else:
            history = []
    except Exception as e:
        logging.error(f"Error reading chat history file: {e}")
        history = []
    history.append({
         "role": role,
         "message": message,
         "timestamp": datetime.now().isoformat()
    })
    try:
        with open(CHAT_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        logging.error(f"Error writing chat history file: {e}")

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        data = request.get_json()
        user_message = data.get("message", "")
        log_chat_message("user", user_message)
        bot_response = get_chatbot_response(user_message)
        log_chat_message("bot", bot_response)
        return jsonify({"response": bot_response})
    return render_template_string(chatbot_html, base_head=base_head)
    
@app.route("/chat_history")
def chat_history():
    """Return the JSON chat conversation history."""
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, "r") as f:
                history = json.load(f)
        else:
            history = []
    except Exception as e:
         logging.error(f"Error reading chat history: {e}")
         history = []
    return jsonify(history)

@app.route("/clear_chat_history", methods=["POST"])
def clear_chat_history():
    """Clear the chat conversation history."""
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, "w") as f:
                json.dump([], f)
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error clearing chat history: {e}")
        return jsonify({"success": False})

if __name__ == '__main__':
    app.run(debug=True)