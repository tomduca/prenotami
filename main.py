import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ChromeOptions
from selenium.webdriver.support.ui import Select
from datetime import datetime
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from time import sleep
import logging
import yaml
import sys
import time
import random
import undetected_chromedriver as udc
from playsound import playsound
from plyer import notification
import threading
import simpleaudio as sa
import numpy as np

load_dotenv()

logging.basicConfig(
    format="%(levelname)s:%(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("/tmp/out.log"), logging.StreamHandler(sys.stdout)],
)

def handle_timeout(driver, attempt):
    try:
        logging.info("Attempting to recover from timeout...")
        if Prenota.is_on_login_page(driver):
            Prenota.login(driver, os.getenv("app_username"), os.getenv("app_password"))
        else:
            driver.refresh()  # Refresh the current page
    except Exception as e:
        logging.error(f"Error while recovering from timeout: {e}")
        if attempt < 3:  # Limit the number of retries
            time.sleep(10)  # Wait for 10 seconds before retrying
            handle_timeout(driver, attempt + 1)
        else:
            driver.quit()
            sys.exit("Failed to recover from timeout after multiple attempts.")

def play_sound():
    fs = 44100  # Sampling rate
    duration = 2  # Duration in seconds of the bell tone

    # Frequencies for a simple bell-like sound
    frequencies = [659.25, 830.61, 1046.50]  # E5, G#5, C6 notes

    # Generate time array
    t = np.linspace(0, duration, int(fs * duration), False)

    # Generate ADSR envelope
    attack_time = 0.1
    decay_time = 0.1
    sustain_level = 0.7
    release_time = 0.8

    attack = np.linspace(0, 1, int(attack_time * fs), False)
    decay = np.linspace(1, sustain_level, int(decay_time * fs), False)
    sustain = np.full(int((duration - attack_time - decay_time - release_time) * fs) + 1, sustain_level)
    release = np.linspace(sustain_level, 0, int(release_time * fs), False)

    envelope = np.concatenate([attack, decay, sustain, release])

    # Generate multiple sine waves, apply envelope and sum them
    tone = sum(np.sin(frequency * t * 2 * np.pi) for frequency in frequencies)
    tone = tone * envelope

    # Normalize to 16-bit range
    audio = tone * (2**15 - 1) / np.max(np.abs(tone))
    audio = audio.astype(np.int16)

    while True:
        # Start playback
        play_obj = sa.play_buffer(audio, 1, 2, fs)

        # Wait for playback to finish
        play_obj.wait_done()

        # Wait for 4 seconds before playing again
        time.sleep(4)

class Prenota:
    @staticmethod
    def check_file_exists(file_name):
        file_path = os.path.join(os.getcwd(), file_name)
        return os.path.isfile(file_path)

    @staticmethod
    def load_config(file_path):
        with open(file_path, "r") as file:
            config = yaml.safe_load(file)
        return config

    @staticmethod
    def check_for_dialog(driver):
        try:
            dialog = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
            )
            button_inside_dialog = dialog.find_element(
                By.XPATH, "//button[contains(text(),'ok')]"
            )
            button_inside_dialog.click()
            logging.info(
                f"Timestamp: {str(datetime.now())} - Scheduling is not available right now."
            )
            return True
        except NoSuchElementException:
            logging.info(
                f"Timestamp: {str(datetime.now())} - Element WlNotAvailable not found. Start filling the forms."
            )
            return False

    @staticmethod
    def fill_citizenship_form(driver, user_config):
        try:
            driver.get("https://prenotami.esteri.it/Services/Booking/791")
            time.sleep(6)
            if not Prenota.check_for_dialog(driver):
                file_location = os.path.join("files/residencia.pdf")
                choose_file = driver.find_elements(By.ID, "File_0")
                choose_file[0].send_keys(file_location)
                privacy_check = driver.find_elements(By.ID, "PrivacyCheck")
                privacy_check[0].click()
                submit = driver.find_elements(By.ID, "btnAvanti")
                submit[0].click()
                with open("files/citizenship_form.html", "w") as f:
                    f.write(driver.page_source)
                return True
        except Exception as e:
            logging.info(f"Exception {e}")
            return False

    @staticmethod
    def fill_passport_form(driver, user_config):
        try:
            time.sleep(10)
            driver.get("https://prenotami.esteri.it/Services/Booking/1319")
            time.sleep(5)

            if not Prenota.check_for_dialog(driver):
                with open("files/passport_form.html", "w") as f:
                    f.write(driver.page_source)

                q0 = Select(driver.find_element(By.ID, "ddls_0"))
                q0.select_by_visible_text(user_config.get("possess_expired_passport"))

                q1 = Select(driver.find_element(By.ID, "ddls_1"))
                q1.select_by_visible_text(user_config.get("possess_expired_passport"))

                q2 = driver.find_element(By.ID, "DatiAddizionaliPrenotante_2___testo")
                q2.send_keys(user_config.get("total_children"))

                q3 = driver.find_element(By.ID, "DatiAddizionaliPrenotante_3___testo")
                q3.send_keys(user_config.get("full_address"))

                q4 = Select(driver.find_element(By.ID, "ddls_4"))
                q4.select_by_visible_text(user_config.get("marital_status"))

                time.sleep(1)

                file0 = driver.find_element(By.XPATH, '//*[@id="File_0"]')
                file0.send_keys(os.getcwd() + "/files/identidade.pdf")

                time.sleep(1)

                file1 = driver.find_element(By.XPATH, '//*[@id="File_1"]')
                file1.send_keys(os.getcwd() + "/files/residencia.pdf")

                checkBox = driver.find_element(By.ID, "PrivacyCheck")
                checkBox.click()

                form_submit = driver.find_element(By.ID, "btnAvanti")
                form_submit.click()

                return True
        except Exception as e:
            logging.info(f"Exception {e}")
            return False

    @staticmethod
    def is_on_login_page(driver):
        try:
            driver.find_element(By.ID, "login-email")
            driver.find_element(By.ID, "login-password")
            return True
        except NoSuchElementException:
            return False

    @staticmethod
    def login(driver, email, password):
        try:
            driver.get("https://prenotami.esteri.it/")
            email_box = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.ID, "login-email"))
            )
            password_box = driver.find_element(By.ID, "login-password")
            email_box.send_keys(email)
            password_box.send_keys(password)
            time.sleep(4)
            button = driver.find_elements(
                By.XPATH, "//button[contains(@class,'button primary g-recaptcha')]"
            )
            button[0].click()
            logging.info(
                f"Timestamp: {str(datetime.now())} - Successfully logged in."
            )
            time.sleep(10)
        except TimeoutException as e:
            logging.error(f"TimeoutException during login: {e}")
            return False
        except Exception as e:
            logging.error(f"Exception during login: {e}")
            return False
        return True

    @staticmethod
    def run(driver):
        if Prenota.check_file_exists("files/residencia.pdf"):
            logging.info(
                f"Timestamp: {str(datetime.now())} - Required files available."
            )
            email = os.getenv("app_username")
            password = os.getenv("app_password")
            
            if not Prenota.login(driver, email, password):
                sys.exit("Failed to login")

            for i in range(200):
                random_number = random.randint(10, 40)

                if Prenota.is_on_login_page(driver):
                    logging.info(
                        "Detected redirection to login page. Attempting to re-login."
                    )
                    if not Prenota.login(driver, email, password):
                        logging.error("Failed to re-login")
                        break

                user_config = Prenota.load_config("parameters.yaml")
                if user_config["request_type"] == "citizenship":
                    if Prenota.fill_citizenship_form(driver, user_config):
                        break
                elif user_config["request_type"] == "passport":
                    if Prenota.fill_passport_form(driver, user_config):
                        break

                time.sleep(random_number)

            # Start playing sound in a separate thread
            threading.Thread(target=play_sound, daemon=True).start()

            # Show a notification
            notification.notify(
                title='Appointment Found',
                message='An appointment is available. Please fill the remaining details.',
                app_name='Prenota Appointment Checker'
            )

            user_input = input(
                f"Timestamp: {str(datetime.now())} - Go ahead and fill manually the rest of the process. "
                f"When finished, type 'quit' to exit the program and close the browser. "
            )
            while True:
                if user_input == "quit":
                    driver.quit()
                    break
        else:
            logging.info(
                "Required files are not available. Check the required files in README.md file. Ending execution."
            )
            sys.exit(0)

if __name__ == "__main__":
    email = os.getenv("app_username")
    password = os.getenv("app_password")

    options = udc.ChromeOptions()
    options.headless = False
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = udc.Chrome(use_subprocess=True, options=options)
    driver.delete_all_cookies()

    Prenota.run(driver)