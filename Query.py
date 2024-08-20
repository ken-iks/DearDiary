# Query.py uses perplexity.ai to generate a summary of the training data

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import time
from bs4 import BeautifulSoup
import re
import unicodedata
import sys
import threading

def clean_text(text):
    # Normalize text to NFC form (you can choose a different form if needed)
    normalized_text = unicodedata.normalize('NFC', text)   
    # Remove all non-visible characters
    cleaned_text = re.sub(r'[\n\r\t]+', ' ', normalized_text) 
    # Replace multiple spaces with a single space
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    # Remove any character outside the BMP (U+0000 to U+FFFF)
    cleaned_text = re.sub(r'[^\u0000-\uFFFF]', '', cleaned_text)
    # Remove leading and trailing whitespace
    cleaned_text = cleaned_text.strip()
    
    return cleaned_text


def enter_text_in_chunks(text, driver, chunk_size=5000, delay=0.1):
    """
    Sends text to a textarea in chunks to avoid overloading it.
    
    Parameters:
    - text: The full text string to be entered.
    - chunk_size: The size of each text chunk (default is 100 characters).
    - delay: Time to wait between sending chunks (in seconds, default is 0.5).
    """
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        while True:
            try:
                # Re-locate the textarea each time to avoid stale element reference
                textarea = driver.find_element(By.XPATH, '//textarea[contains(@class, "overflow-auto max-h-[45vh] outline-none w-full font-sans caret-superDuper resize-none")]')
                textarea.send_keys(chunk)
                break  # Exit the while loop if successful
            except StaleElementReferenceException:
                print("Stale element reference caught, retrying...")
                time.sleep(1)  # Wait a moment before retrying

stop_spinner = False
spinner_message = "Processing..."

def loading_spinner():
    spinner = ['|', '/', '-', '\\']
    idx = 0
    while not stop_spinner:
        sys.stdout.write('\r' + spinner[idx] + ' ' + spinner_message)
        sys.stdout.flush()
        idx = (idx + 1) % len(spinner)
        time.sleep(0.1)
    sys.stdout.write('\rDone!\n')
    sys.stdout.flush()

def analyzeText(text, driver):
    global stop_spinner, spinner_message

    text = clean_text(text)

    try:
        # Start the loading spinner for the text entry phase
        stop_spinner = False
        spinner_message = "Entering text into the input field..."
        spinner_thread = threading.Thread(target=loading_spinner)
        spinner_thread.start()

        # Wait for the textarea to be visible and interactable
        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.XPATH, '//textarea[contains(@class, "overflow-auto max-h-[45vh] outline-none w-full font-sans caret-superDuper resize-none")]'))
        )
        
        # Send the text in chunks
        enter_text_in_chunks(text, driver)
        
        # Locate the textarea again before sending the return key
        textarea = driver.find_element(By.XPATH, '//textarea[contains(@class, "overflow-auto max-h-[45vh] outline-none w-full font-sans caret-superDuper resize-none")]')
        textarea.send_keys(Keys.RETURN)  # Simulate pressing the Enter key

        # Notify that text entry is complete
        stop_spinner = True
        spinner_thread.join()
        print("Text has been fully entered.")

        # Start the loading spinner for the response generation phase
        stop_spinner = False
        spinner_message = "Waiting for the response to be generated..."
        spinner_thread = threading.Thread(target=loading_spinner)
        spinner_thread.start()

        # Wait until the response is generated and visible
        response_div = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'prose dark:prose-invert')]"))
        )

        # Initialize a variable to track content length
        content_length = 0
        max_attempts = 30  # Maximum number of attempts to check for content stabilization
        attempts = 0

        while attempts < max_attempts:
            time.sleep(3)
            # Re-locate the element to avoid stale reference
            response_div = driver.find_element(By.XPATH, "//div[contains(@class, 'prose dark:prose-invert')]")
            new_content_length = len(response_div.text)

            if new_content_length == content_length:
                break  # Content length has stabilized, assuming loading is done

            content_length = new_content_length
            attempts += 1
            time.sleep(3)  # Short sleep to allow more content to load

        # Notify that the response is fully loaded
        stop_spinner = True
        spinner_thread.join()
        print("Response has been fully generated.")

        # Extract the response using BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        response_div = soup.find("div", class_="prose dark:prose-invert inline leading-normal break-words min-w-0 [word-break:break-word]")

        # Return the extracted response text if found
        if response_div:
            raw_text = response_div.get_text(separator="\n").strip()
           
            # Process the text to clean it up while retaining structure
            lines = raw_text.splitlines()
            formatted_lines = []
            current_section = []

            for line in lines:
                stripped_line = line.strip()
                if stripped_line:  # Only consider non-empty lines
                    current_section.append(stripped_line)
                else:
                    if current_section:
                        formatted_lines.append(" ".join(current_section))  # Join lines within a section
                        current_section = []
                        formatted_lines.append("")  # Add an empty line for spacing between sections

            # If there's any content left in the last section, add it
            if current_section:
                formatted_lines.append(" ".join(current_section))

            # Join sections with double newlines to keep structure between paragraphs
            cleaned_text = "\n".join(formatted_lines)

            return cleaned_text
        else:
            return "Response not found or the format has changed."

    except Exception as e:
        stop_spinner = True
        spinner_thread.join()
        return f"An error occurred: {str(e)}"





