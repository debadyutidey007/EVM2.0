-- ==========================================================
-- Step 1: Create Database and Select It
-- ==========================================================
CREATE DATABASE IF NOT EXISTS E_Voting_System;
USE E_Voting_System;

-- ==========================================================
-- Step 2: Create Tables
-- ==========================================================

-- 2.1. Create the "states" table.
CREATE TABLE IF NOT EXISTS states (
    state_id INT AUTO_INCREMENT PRIMARY KEY,
    state_name VARCHAR(255) NOT NULL
) ENGINE = InnoDB;

-- 2.2. Create the "regions" table that references "states".
CREATE TABLE IF NOT EXISTS regions (
    region_id INT AUTO_INCREMENT PRIMARY KEY,
    region_name VARCHAR(255) NOT NULL,
    state_id INT NOT NULL,
    FOREIGN KEY (state_id) REFERENCES states(state_id) ON DELETE CASCADE
) ENGINE = InnoDB;

-- 2.3. Create the "constituencies" table that references "regions".
CREATE TABLE IF NOT EXISTS constituencies (
    constituency_id INT AUTO_INCREMENT PRIMARY KEY,
    constituency_name VARCHAR(255) NOT NULL,
    region_id INT NOT NULL,
    FOREIGN KEY (region_id) REFERENCES regions(region_id) ON DELETE CASCADE
) ENGINE = InnoDB;

-- 2.4. Create the "candidates" table that references "constituencies".
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_name VARCHAR(255) NOT NULL,
    party VARCHAR(255),
    manifesto TEXT,
    constituency_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id) ON DELETE CASCADE
) ENGINE = InnoDB;

-- 2.5. Create the "voters" table.
--    (Note: voters do not log in using a password—instead, they use their voter_identifier.
--     However, the password_hash field is defined as NOT NULL so we insert an empty string for voters.)
CREATE TABLE voters (
    voter_id INT NOT NULL AUTO_INCREMENT,
    voter_username VARCHAR(255) NOT NULL,
    voter_identifier VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'Voter',
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    otp_secret VARCHAR(32) NOT NULL,
    PRIMARY KEY (voter_id)
) ENGINE = InnoDB;

-- 2.6. Create the "admins" table.
--    (Admins use a password to log in. Their usernames can be the same as those in the voters table.)
CREATE TABLE IF NOT EXISTS admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    admin_username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB;

-- 2.7. Create the "elections" table.
CREATE TABLE IF NOT EXISTS elections (
    election_id INT AUTO_INCREMENT PRIMARY KEY,
    election_name VARCHAR(255) NOT NULL,
    start_date DATETIME NOT NULL,
    end_date DATETIME NOT NULL,
    status ENUM('upcoming','ongoing','completed') DEFAULT 'upcoming',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB;

-- 2.8. Create the "votes" table that references voters, candidates, elections, and constituencies.
CREATE TABLE IF NOT EXISTS votes (
    vote_id INT AUTO_INCREMENT PRIMARY KEY,
    voter_id INT NOT NULL,
    candidate_id INT NOT NULL,
    election_id INT NOT NULL,
    constituency_id INT NOT NULL,
    vote_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    vote_hash VARCHAR(255) NOT NULL,
    FOREIGN KEY (voter_id) REFERENCES voters(voter_id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY (election_id) REFERENCES elections(election_id) ON DELETE CASCADE,
    FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id) ON DELETE CASCADE
) ENGINE = InnoDB;

-- 2.9. Create the "audit_logs" table that references voters.
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(255) NOT NULL,
    details TEXT,
    log_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES voters(voter_id) ON DELETE SET NULL
) ENGINE = InnoDB;

-- Step 3: Insert Sample Data for Geographic Hierarchy

-- 3.1 Insert sample states.
INSERT INTO states (state_name) VALUES
  ('andhra pradesh'),
  ('Arunachal Pradesh'),
  ('Assam'),
  ('Bihar'),
  ('Chattisgarh'),
  ('Goa');

-- 3.2 Insert sample regions for each state.

-- For Andhra Pradesh (state_id = 1)
INSERT INTO regions (region_name, state_id) VALUES
  ('ANANTPUR', 1),
  ('GUNTOOR', 1),
  ('KURNOOL', 1),
  ('SRIKAKULAM', 1),
  ('WEST GODAVARI', 1);

-- For Arunachal Pradesh (state_id = 2)
INSERT INTO regions (region_name, state_id) VALUES
  ('ANJAW', 2),
  ('EAST KAMENG', 2),
  ('KRA - DAADI', 2),
  ('LOHIT', 2),
  ('LOWER - SIANG', 2);

-- For Assam (state_id = 3)
INSERT INTO regions (region_name, state_id) VALUES
  ('BAJALI', 3),
  ('BIJNI', 3),
  ('BOGAIGAON', 3),
  ('CHARAIDEO (SONARI)', 3),
  ('DHANSIRI', 3);

-- For Bihar (state_id = 4)
INSERT INTO regions (region_name, state_id) VALUES
  ('ARARIA', 4),
  ('BANKA', 4),
  ('BHOJPUR', 4),
  ('GAYA', 4),
  ('JAMUI', 4);

-- For Chattisgarh (state_id = 5)
INSERT INTO regions (region_name, state_id) VALUES
  ('BALOD', 5),
  ('BASTAR (JAGDALPUR)', 5),
  ('BILASPUR', 5),
  ('DURG', 5),
  ('JASHPUR', 5);

-- For Goa (state_id = 6)
INSERT INTO regions (region_name, state_id) VALUES
  ('NORTH GOA', 6),
  ('SOUTH GOA', 6);

-- 3.3 Insert sample constituencies for each region.

-- Andhra Pradesh:
-- Region: ANANTPUR (assumed region_id = 1)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Anantpur Urban', 1),
  ('Dharmavaram', 1),
  ('Guntal', 1);

-- Region: GUNTOOR (assumed region_id = 2)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Bapatala', 2),
  ('Chilakaluripet', 2),
  ('Gurajala', 2);

-- Region: KURNOOL (assumed region_id = 3)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Adoni', 3),
  ('Allagadda', 3),
  ('Alur', 3);

-- Region: SRIKAKULAM (assumed region_id = 4)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('AMADALAVALASA', 4),
  ('ETCHERLA', 4),
  ('ICHCHAPURA', 4);

-- Region: WEST GODAVARI (assumed region_id = 5)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Achanta', 5),
  ('Bhimavaram', 5),
  ('Chintalapudi (SC)', 5);

-- Arunachal Pradesh:
-- Region: ANJAW (assumed region_id = 6)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Haluiyang', 6);

-- Region: EAST KAMENG (assumed region_id = 7)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Bameng', 7),
  ('Chayangtajo (ST)', 7),
  ('SEPPA EAST (ST)', 7);

-- Region: KRA - DAADI (assumed region_id = 8)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('PALIN (ST)', 8),
  ('TALI (ST)', 8);

-- Region: LOHIT (assumed region_id = 9)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('TEZU (ST)', 9);

-- Region: LOWER - SIANG (assumed region_id = 10)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('LIKABALI', 10),
  ('NARI - KOYU', 10);

-- Assam:
-- Region: BAJALI (assumed region_id = 11)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Bhabanipur', 11),
  ('Patacharkuchi', 11);

-- Region: BIJNI (assumed region_id = 12)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Bijjni', 12);

-- Region: BOGAIGAON (assumed region_id = 13)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Bongaigaon', 13);

-- Region: CHARAIDEO (SONARI) (assumed region_id = 14)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Mahmara', 14),
  ('Sonari', 14);

-- Region: DHANSIRI (assumed region_id = 15)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Sarupathar', 15);

-- Bihar:
-- Region: ARARIA (assumed region_id = 16)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Forbesganj', 16),
  ('Jokihat', 16),
  ('Narpatgan', 16);

-- Region: BANKA (assumed region_id = 17)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Amarpur', 17),
  ('Belhar', 17),
  ('Dhoraiya (SC)', 17);

-- Region: BHOJPUR (assumed region_id = 18)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Agiaon (SC)', 18),
  ('Arrah', 18),
  ('Barhara', 18);

-- Region: GAYA (assumed region_id = 19)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Atri', 19),
  ('Barachatti (SC)', 19),
  ('Belaganj', 19);

-- Region: JAMUI (assumed region_id = 20)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('CHAKAI', 20),
  ('JHAJHA', 20),
  ('SIKANDRA (SC)', 20);

-- Chattisgarh:
-- Region: BALOD (assumed region_id = 21)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Dondi Lohara (ST)', 21),
  ('Gunderdehi', 21),
  ('Sanjhari Balod', 21);

-- Region: BASTAR (JAGDALPUR) (assumed region_id = 22)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Bastar (ST)', 22),
  ('Chitrakot (ST)', 22),
  ('Jagdalpur', 22);

-- Region: BILASPUR (assumed region_id = 23)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Beltara', 23),
  ('Bilha', 23),
  ('Kota', 23);

-- Region: DURG (assumed region_id = 24)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Ahiwara (SC)', 24),
  ('Bhilai Nagar', 24),
  ('Durg City', 24);

-- Region: JASHPUR (assumed region_id = 25)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Jashpur (ST)', 25),
  ('Kunkuri (ST)', 25),
  ('Pathalgaon (ST)', 25);

-- Goa:
-- Region: NORTH GOA (assumed region_id = 26)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Aldona', 26),
  ('Bicholim', 26),
  ('Calangute', 26);

-- Region: SOUTH GOA (assumed region_id = 27)
INSERT INTO constituencies (constituency_name, region_id) VALUES
  ('Mormugao', 27),
  ('Fatorda', 27),
  ('Dabolim', 27);


-- Andhra Pradesh
-- For constituency 'Anantpur Urban' (assumed constituency_id = 1)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Juhi Chawla - Anantpur Urban', 'YSR Congress Party', 'Committed to local development and welfare.', 1),
('Alakh Pandey - Anantpur Urban', 'Telugu Desam Party', 'Focused on progressive reforms and growth.', 1),
('Abhishek Dindha - Anantpur Urban', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 1),
('Samprit Nandy - Anantpur Urban', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 1);

-- For constituency 'Dharmavaram' (assumed constituency_id = 2)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Rajdip Routh - Dharmavaram', 'YSR Congress Party', 'Promoting rural infrastructure and education.', 2),
('Rekha Dey - Dharmavaram', 'Telugu Desam Party', 'Enhancing healthcare and public services.', 2),
('Akash Singh - Dharmavaram', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 2),
('Abhishek Jha - Dharmavaram', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 2);

-- For constituency 'Guntal' (assumed constituency_id = 3)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Akash Dodeja - Guntal', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 3),
('Mihir Dey - Guntal', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 3),
('Sanjoy Sen - Guntal', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 3),
('Rekha Rathore - Guntal', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 3);


-- For Constituency 'Bapatala' (assumed constituency_id = 4)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Rema Biswas - Bapatala', 'YSR Congress Party', 'Committed to local development and welfare.', 4),
('Narendra Modi - Bapatala', 'Telugu Desam Party', 'Focused on progressive reforms and growth.', 4),
('Nirav Modi - Bapatala', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 4),
('Rishika Sen - Bapatala', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 4);

-- For constituency 'Chilakaluripet' (assumed constituency_id = 5)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Anant Ambani - Chilakaluripet', 'YSR Congress Party', 'Promoting rural infrastructure and education.', 5),
('Sanjib Modi - Chilakaluripet', 'Telugu Desam Party', 'Enhancing healthcare and public services.', 5),
('Sandip Goyenka - Chilakaluripet', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 5),
('Rishika Jaiswal - Chilakaluripet', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 5);

-- For constituency 'Gurajala' (assumed constituency_id = 6)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Rishika Madav - Gurajala', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 6),
('Tanmay Singh - Gurajala', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 6),
('Tanmay Bhat - Gurajala', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 6),
('Sudhriti Saha - Gurajala', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 6);

-- For constituency 'Adoni' (assumed constituency_id = 7)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Joginder Singh - Adoni', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 7),
('Neeraj Walia - Adoni', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 7),
('Moumita Sen - Adoni', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 7),
('Ruchika Mallick - Adoni', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 7);

-- For constituency 'Allagadda' (assumed constituency_id = 8)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Ranveer Alabadia - Allagadda', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 8),
('Mousumi Datta - Allagadda', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 8),
('Moumita Sen - Allagadda', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 8),
('Ruchika Mallick - Allagadda', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 8);

-- For constituency 'Alur' (assumed constituency_id = 9)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Sanjoy Pandey - Alur', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 9),
('Ranbir Ganguly - Alur', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 9),
('Mihir Gangopadhay - Alur', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 9),
('Samay Raina - Alur', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 9);

-- For constituency 'AMADALAVALASA' (assumed constituency_id = 10)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Kavya - AMADALAVALASA', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 10),
('Shyam - AMADALAVALASA', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 10),
('Arundhati - AMADALAVALASA', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 10),
('Aarohi - AMADALAVALASA', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 10);

-- For constituency 'ETCHERLA' (assumed constituency_id = 11)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Ankita Dey - ETCHERLA', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 11),
('Riya Pandey - ETCHERLA', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 11),
('Subhashis Bose - ETCHERLA', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 11),
('Sarukh Khan - ETCHERLA', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 11);

-- For constituency 'ICHCHAPURA' (assumed constituency_id = 12)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Vivan - ICHCHAPURA', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 12),
('Virat - ICHCHAPURA', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 12),
('Yogesh - ICHCHAPURA', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 12),
('Yash - ICHCHAPURA', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 12);

-- For constituency 'Achanta' (assumed constituency_id = 13)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Vibhav - Achanta', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 13),
('Ujjwal - Achanta', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 13),
('Tejas - Achanta', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 13),
('Tanish - Achanta', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 13);

-- For constituency 'Bhimavaram' (assumed constituency_id = 14)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Tanmay Ojha - Bhimavaram', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 14),
('Siddharth - Bhimavaram', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 14),
('Shiv - Bhimavaram', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 14),
('Shaan - Bhimavaram', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 14);


-- For constituency 'Chintalapudi (SC)' (assumed constituency_id = 15)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Sarthak - Chintalapudi (SC)', 'YSR Congress Party', 'Driving sustainable agricultural growth.', 15),
('Sanjiv - Chintalapudi (SC)', 'Telugu Desam Party', 'Focusing on modernizing local industries.', 15),
('Samir - Chintalapudi (SC)', 'Jana Sena Party (JSP)', 'Promoting rural infrastructure and education.', 15),
('Sahar - Chintalapudi (SC)', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 15);

-- Arunachal Pradesh
-- For constituency 'Haluiyang' (assumed constituency_id = 16)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Sarthak - Haluiyang', 'Janata Dal (Secular) (JD(S))', 'Driving sustainable agricultural growth.', 16),
('Sanjiv - Haluiyang', 'People Party of Arunachal (PPA)', 'Focusing on modernizing local industries.', 16),
('Samir - Haluiyang', 'National People Party (NPP)', 'Promoting rural infrastructure and education.', 16),
('Sahar - Haluiyang', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 16);

-- For constituency 'Bameng' (assumed constituency_id = 17)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Rishabh - Bameng', 'Janata Dal (Secular) (JD(S))', 'Driving sustainable agricultural growth.', 17),
('Rahul - Bameng', 'People Party of Arunachal (PPA)', 'Focusing on modernizing local industries.', 17),
('Pranav - Bameng', 'National People Party (NPP)', 'Promoting rural infrastructure and education.', 17),
('Pavan - Bameng', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 17);

-- For constituency 'Chayangtajo (ST)' (assumed constituency_id = 18)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Om - Chayangtajo (ST)', 'Janata Dal (Secular) (JD(S))', 'Driving sustainable agricultural growth.', 18),
('Nayan - Chayangtajo (ST)', 'People Party of Arunachal (PPA)', 'Focusing on modernizing local industries.', 18),
('Mehul - Chayangtajo (ST)', 'National People Party (NPP)', 'Promoting rural infrastructure and education.', 18),
('Manav - Chayangtajo (ST)', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 18);


-- For constituency 'SEPPA EAST (ST)' (assumed constituency_id = 19)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Lavi - SEPPA EAST (ST)', 'Janata Dal (Secular) (JD(S))', 'Driving sustainable agricultural growth.', 19),
('Kunal - SEPPA EAST (ST)', 'People Party of Arunachal (PPA)', 'Focusing on modernizing local industries.', 19),
('Kripa - SEPPA EAST (ST)', 'National People Party (NPP)', 'Promoting rural infrastructure and education.', 19),
('Kavi - SEPPA EAST (ST)', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 19);

-- For constituency 'PALIN (ST)' (assumed constituency_id = 20)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Kabir - SEPPA EAST (ST)', 'Janata Dal (Secular) (JD(S))', 'Driving sustainable agricultural growth.', 20),
('Jagrav - SEPPA EAST (ST)', 'People Party of Arunachal (PPA)', 'Focusing on modernizing local industries.', 20),
('Harsha - SEPPA EAST (ST)', 'National People Party (NPP)', 'Promoting rural infrastructure and education.', 20),
('Gaurav - SEPPA EAST (ST)', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 120);

-- For constituency 'TALI (ST)' (assumed constituency_id = 21)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Eeshan - TALI (ST)', 'Janata Dal (Secular) (JD(S))', 'Driving sustainable agricultural growth.', 21),
('Diya - TALI (ST)', 'People Party of Arunachal (PPA)', 'Focusing on modernizing local industries.', 21),
('Dev - TALI (ST)', 'National People Party (NPP)', 'Promoting rural infrastructure and education.', 21),
('Daksh - TALI (ST)', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 21);

-- For constituency 'TEZU (ST)' (assumed constituency_id = 22)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Charan - TEZU (ST)', 'Janata Dal (Secular) (JD(S))', 'Driving sustainable agricultural growth.', 22),
('Bhanu - TEZU (ST)', 'People Party of Arunachal (PPA)', 'Focusing on modernizing local industries.', 22),
('Arpit - TEZU (ST)', 'National People Party (NPP)', 'Promoting rural infrastructure and education.', 22),
('Anmol - TEZU (ST)', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 22);

-- For constituency 'LIKABALI' (assumed constituency_id = 23)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Akshay - LIKABALI', 'Janata Dal (Secular) (JD(S))', 'Driving sustainable agricultural growth.', 23),
('Aashir - LIKABALI', 'People Party of Arunachal (PPA)', 'Focusing on modernizing local industries.', 23),
('Aarya - LIKABALI', 'National People Party (NPP)', 'Promoting rural infrastructure and education.', 23),
('Aakash - LIKABALI', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 23);

-- For constituency 'NARI - KOYU' (assumed constituency_id = 24)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Aadi - NARI - KOYU', 'Janata Dal (Secular) (JD(S))', 'Driving sustainable agricultural growth.', 24),
('Vandana - NARI - KOYU', 'People Party of Arunachal (PPA)', 'Focusing on modernizing local industries.', 24),
('Urmila - NARI - KOYU', 'National People Party (NPP)', 'Promoting rural infrastructure and education.', 24),
('Tanya - NARI - KOYU', 'Bharatiya Janata Party (BJP)', 'Enhancing healthcare and public services.', 24);

-- Assam
-- For constituency 'Bhabanipur' (assumed constituency_id = 25)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Sunita - Bhabanipur', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 25),
('Sumana - Bhabanipur', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 25),
('Sneha - Bhabanipur', 'Asom Gana Parishad (AGP)', 'Promoting rural infrastructure and education.', 25),
('Smita - Bhabanipur', 'Raijor Dal', 'Enhancing healthcare and public services.', 25);

-- For constituency 'Patacharkuchi' (assumed constituency_id = 26)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Simran - Patacharkuch', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 26),
('Shreya - Patacharkuch', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 26),
('Shalini - Patacharkuch', 'Asom Gana Parishad (AGP)', 'Promoting rural infrastructure and education.', 26),
('Seema - Patacharkuch', 'Raijor Dal', 'Enhancing healthcare and public services.', 26);


-- For constituency 'Bijjni' (assumed constituency_id = 27)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Sapna - Bijjni', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 27),
('Sangeeta - Bijjni', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 27),
('Riya - Bijjni', 'Asom Gana Parishad (AGP)', 'Promoting rural infrastructure and education.', 27),
('Renu - Bijjni', 'Raijor Dal', 'Enhancing healthcare and public services.', 27);

-- For constituency 'Bongaigaon' (assumed constituency_id = 28)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Rekha - Bongaigaon', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 28),
('Radha - Bongaigaon', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 28),
('Priya - Bongaigaon', 'Asom Gana Parishad (AGP)', 'Promoting rural infrastructure and education.', 28),
('Prachi - Bongaigaon', 'Raijor Dal', 'Enhancing healthcare and public services.', 28);

-- For constituency 'Mahmara' (assumed constituency_id = 29)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Poonam - Mahmara', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 29),
('Pallavi - Mahmara', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 29),
('Nisha - Mahmara', 'Asom Gana Parishad (AGP)', 'Promoting rural infrastructure and education.', 29),
('Neha - Mahmara', 'Raijor Dal', 'Enhancing healthcare and public services.', 29);

-- For constituency 'Sonari' (assumed constituency_id = 30)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Meena - Sonari', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 30),
('Malini - Sonari', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 30),
('Madhuri - Sonari', 'Asom Gana Parishad (AGP)', 'Promoting rural infrastructure and education.', 30),
('Lata - Sonari', 'Raijor Dal', 'Enhancing healthcare and public services.', 30);

-- For constituency 'Sarupathar' (assumed constituency_id = 31)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Komal - Sarupathar', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 31),
('Kirti - Sarupathar', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 31),
('Kavita - Sarupathar', 'Asom Gana Parishad (AGP)', 'Promoting rural infrastructure and education.', 31),
('Jyoti - Sarupathar', 'Raijor Dal', 'Enhancing healthcare and public services.', 31);

-- Bihar
-- For constituency 'Forbesganj' (assumed constituency_id = 32)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Rekha - Forbesganj', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 32),
('Radha - Forbesganj', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 32),
('Priya - Forbesganj', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 32),
('Prachi - Forbesganj', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 32);

-- For constituency 'Jokihat' (assumed constituency_id = 33)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Poonam - Jokihat', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 33),
('Pallavi - Jokihat', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 33),
('Nisha - Jokihat', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 33),
('Neha - Jokihat', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 33);

-- For constituency 'Narpatgan' (assumed constituency_id = 34)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Meena - Narpatgan', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 34),
('Malini - Narpatgan', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 34),
('Madhuri - Narpatgan', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 34),
('Lata - Narpatgan', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 34);

-- For constituency 'Amarpur' (assumed constituency_id = 35)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Komal - Amarpur', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 35),
('Kriti - Amarpur', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 35),
('Kavita - Amarpur', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 35),
('Jyoti - Amarpur', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 35);


-- For constituency 'Belhar' (assumed constituency_id = 36)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Jaya - Belhar', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 36),
('Ishita - Belhar', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 36),
('Himani - Belhar', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 36),
('Harini - Belhar', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 36);


-- For constituency 'Dhoraiya (SC)' (assumed constituency_id = 37)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Geeta - Dhoraiya (SC)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 37),
('Esha - Dhoraiya (SC)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 37),
('Damini - Dhoraiya (SC)', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 37),
('Deepika - Dhoraiya (SC)', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 37);


-- For constituency 'Agiaon (SC)' (assumed constituency_id = 38)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Chitra - Agiaon (SC)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 38),
('Bhavna - Agiaon (SC)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 38),
('Asmita - Agiaon (SC)', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 38),
('Arpita - Agiaon (SC)', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 38);


-- For constituency 'Arrah' (assumed constituency_id = 39)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Anjali - Arrah', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 39),
('Ananya - Arrah', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 39),
('Amrita - Arrah', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 39),
('Alka - Arrah', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 39);


-- For constituency 'Barhara' (assumed constituency_id = 40)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Akshita - Barhara', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 40),
('Aarti - Barhara', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 40),
('Varun - Barhara', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 40),
('Tarun - Barhara', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 40);


-- For constituency 'Atri' (assumed constituency_id = 41)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Suresh - Atri', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 41),
('Siddharth - Atri', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 41),
('Shankar - Atri', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 41),
('Saurabh - Atri', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 41);


-- For constituency 'Barachatti (SC)' (assumed constituency_id = 42)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Sanjay - Barachatti (SC)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 42),
('Sameer - Barachatti (SC)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 42),
('Sahil - Barachatti (SC)', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 42),
('Rohit - Barachatti (SC)', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 42);


-- For constituency 'Belaganj' (assumed constituency_id = 43)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Rakesh - Belaganj', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 43),
('Rajesh - Belaganj', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 43),
('Rahul - Belaganj', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 43),
('Prakash - Belaganj', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 43);


-- For constituency 'CHAKAI' (assumed constituency_id = 44)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Piyush - CHAKAI', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 44),
('Parth - CHAKAI', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 44),
('Omkar - CHAKAI', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 44),
('Nishant - CHAKAI', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 44);


-- For constituency 'JHAJHA' (assumed constituency_id = 45)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Naresh - JHAJHA', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 45),
('Mukesh - JHAJHA', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 45),
('Manish - JHAJHA', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 45),
('Mahesh - JHAJHA', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 45);


-- For constituency 'SIKANDRA (SC)' (assumed constituency_id = 46)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Lalit - SIKANDRA (SC)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 46),
('Kishore - SIKANDRA (SC)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 46),
('Kiran - SIKANDRA (SC)', 'Janata Dal (United) [JD(U)]', 'Promoting rural infrastructure and education.', 46),
('Kartik - SIKANDRA (SC)', 'Rashtriya Janata Dal (RJD)', 'Enhancing healthcare and public services.', 46);

-- Chattishgarh
-- For constituency 'Dondi Lohara (ST)' (assumed constituency_id = 47)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Jayesh - Dondi Lohara (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 47),
('Jatin - Dondi Lohara (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 47),
('Ishaan - Dondi Lohara (ST)', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 47),
('Hemant - Dondi Lohara (ST)', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 47);


-- For constituency 'Gunderdehi' (assumed constituency_id = 48)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Harsh - Gunderdehi', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 48),
('Gopal - Gunderdehi', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 48),
('Gautam - Gunderdehi', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 48),
('Eshan - Gunderdehi', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 48);


-- For constituency 'Sanjhari Balod' (assumed constituency_id = 49)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Dhruv - Sanjhari Balod', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 49),
('Dinesh - Sanjhari Balod', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 49),
('Deepak - Sanjhari Balod', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 49),
('Darshan - Sanjhari Balod', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 49);


-- For constituency 'Bastar (ST)' (assumed constituency_id = 50)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Chandan - Bastar (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 50),
('Chetan - Bastar (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 50),
('Bhavesh - Bastar (ST)', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 50),
('Ashish - Bastar (ST)', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 50);


-- For constituency 'Chitrakot (ST)' (assumed constituency_id = 51)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Arvind - Chitrakot (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 51),
('Anish - Chitrakot (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 51),
('Aniket - Chitrakot (ST)', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 51),
('Abhinav - Chitrakot (ST)', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 51);


-- For constituency 'Jagdalpur' (assumed constituency_id = 52)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Arjun - Jagdalpur', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 52),
('Aakash - Jagdalpur', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 52),
('Aditya - Jagdalpur', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 52),
('Aarav - Jagdalpur', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 52);


-- For constituency 'Beltara' (assumed constituency_id = 53)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Abhay - Beltara', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 53),
('Abhiram - Beltara', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 53),
('Ajay - Beltara', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 53),
('Akashdeep - Beltara', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 53);


-- For constituency 'Bilha' (assumed constituency_id = 54)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Amar - Bilha', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 54),
('Amit - Bilha', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 54),
('Anand - Bilha', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 54),
('Anurag - Bilha', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 54);


-- For constituency 'Kota' (assumed constituency_id = 55)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Ashwin - Kota', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 55),
('Atul - Kota', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 55),
('Avinash - Kota', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 55),
('Bhuvan - Kota', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 55);


-- For constituency 'Ahiwara (SC)' (assumed constituency_id = 56)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Chandresh - Ahiwara (SC)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 56),
('Dhananjay - Ahiwara (SC)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 56),
('Chiranjeev - Ahiwara (SC)', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 56),
('Devendra - Ahiwara (SC)', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 56);


-- For constituency 'Bhilai Nagar' (assumed constituency_id = 57)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Dipesh - Bhilai Nagar', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 57),
('Eklavya - Bhilai Nagar', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 57),
('Ganesh - Bhilai Nagar', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 57),
('Girish - Bhilai Nagar', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 57);


-- For constituency 'Durg City' (assumed constituency_id = 58)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Govind - Durg City', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 58),
('Harendra - Durg City', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 58),
('Hitesh - Durg City', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 58),
('Hitesh - Durg City', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 58);


-- For constituency 'Jashpur (ST)' (assumed constituency_id = 59)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Inder - Jashpur (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 59),
('Jaideep - Jashpur (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 59),
('Jaipal - Jashpur (ST)', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 59),
('Jeetendra - Jashpur (ST)', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 59);


-- For constituency 'Kunkuri (ST)' (assumed constituency_id = 60)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Kailash - Kunkuri (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 60),
('Kamal - Kunkuri (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 60),
('Kanaiya - Kunkuri (ST)', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 60),
('Keshav - Kunkuri (ST)', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 60);


-- For constituency 'Pathalgaon (ST)' (assumed constituency_id = 61)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Kuldeep - Pathalgaon (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 61),
('Lakshman - Pathalgaon (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 61),
('Lokesh - Pathalgaon (ST)', 'Bahujan Samaj Party (BSP)', 'Promoting rural infrastructure and education.', 61),
('Madan - Pathalgaon (ST)', 'Communist Party of India (CPI)', 'Enhancing healthcare and public services.', 61);

-- Goa
-- For constituency 'Aldona' (assumed constituency_id = 62)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Jayesh - Pathalgaon (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 62),
('Jatin - Pathalgaon (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 62),
('Ishaan - Pathalgaon (ST)', 'Goa Forward Party (GFP))', 'Promoting rural infrastructure and education.', 62),
('Hemant - Pathalgaon (ST)', 'Revolutionary Goans Party (RGP)', 'Enhancing healthcare and public services.', 62);


-- For constituency 'Bicholim' (assumed constituency_id = 63)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Jayesh - Pathalgaon (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 63),
('Jatin - Pathalgaon (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 63),
('Ishaan - Pathalgaon (ST)', 'Goa Forward Party (GFP)', 'Promoting rural infrastructure and education.', 63),
('Hemant - Pathalgaon (ST)', 'Revolutionary Goans Party (RGP)', 'Enhancing healthcare and public services.', 63);

-- For constituency 'Calangute' (assumed constituency_id = 64)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Jayesh - Pathalgaon (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 64),
('Jatin - Pathalgaon (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 64),
('Ishaan - Pathalgaon (ST)', 'Goa Forward Party (GFP)', 'Promoting rural infrastructure and education.', 64),
('Hemant - Pathalgaon (ST)', 'Revolutionary Goans Party (RGP)', 'Enhancing healthcare and public services.', 64);

-- For constituency 'Mormugao' (assumed constituency_id = 65)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Jayesh - Pathalgaon (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 65),
('Jatin - Pathalgaon (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 65),
('Ishaan - Pathalgaon (ST)', 'Goa Forward Party (GFP)', 'Promoting rural infrastructure and education.', 65),
('Hemant - Pathalgaon (ST)', 'Revolutionary Goans Party (RGP)', 'Enhancing healthcare and public services.', 65);

-- For constituency 'Fatorda' (assumed constituency_id = 66)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Jayesh - Pathalgaon (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 66),
('Jatin - Pathalgaon (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 66),
('Ishaan - Pathalgaon (ST)', 'Goa Forward Party (GFP)', 'Promoting rural infrastructure and education.', 66),
('Hemant - Pathalgaon (ST)', 'Revolutionary Goans Party (RGP)', 'Enhancing healthcare and public services.', 66);

-- For constituency 'Dabolim' (assumed constituency_id = 67)
INSERT INTO candidates (candidate_name, party, manifesto, constituency_id) VALUES
('Jayesh - Pathalgaon (ST)', 'Bharatiya Janata Party (BJP)', 'Driving sustainable agricultural growth.', 67),
('Jatin - Pathalgaon (ST)', 'Indian National Congress (INC)', 'Focusing on modernizing local industries.', 67),
('Ishaan - Pathalgaon (ST)', 'Goa Forward Party (GFP)', 'Promoting rural infrastructure and education.', 67),
('Hemant - Pathalgaon (ST)', 'Revolutionary Goans Party (RGP)', 'Enhancing healthcare and public services.', 67);

INSERT INTO admins (admin_username, password) VALUES
(Debadyuti Dey', 'DEBA4400'),
('Soumyajit Nandy', 'Soumo123'),
('Rajdip Routh', 'RajLovesMisty');