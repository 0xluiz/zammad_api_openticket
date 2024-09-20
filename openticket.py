import os
import re
import json
import requests
import shutil
import logging
import zipfile
import base64
from datetime import datetime
from collections import defaultdict
import urllib.parse  # For URL encoding

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(asctime)s - %(message)s')

# Load configuration from JSON file
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Extract the API configuration
api_url = config['api_config']['zammad_api_url']
api_token = config['api_config']['api_token']
headers = config['api_config']['headers']
headers['Authorization'] = f"Bearer {api_token}"

# Extract folder paths
source_folder = config['folder_paths']['source_folder']
processed_folder = config['folder_paths']['processed_folder']
temp_unzip_folder = config['folder_paths']['temp_unzip_folder']

# Extract ticket settings
group = config['ticket_settings']['group']
customertype = config['ticket_settings']['customertype']
title_template = config['ticket_settings']['title_template']
subject_template = config['ticket_settings']['subject_template']
body_template = config['ticket_settings']['body_template']

# Create necessary folders if they don't exist
for folder in [processed_folder, temp_unzip_folder]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_files_in_folder(folder_path):
    """Get list of zip files in the given folder."""
    return [f for f in os.listdir(folder_path) if f.endswith('.zip') and os.path.isfile(os.path.join(folder_path, f))]

def extract_client_name(file_name):
    """Extract the client or organization name from the ZIP file name (assuming it's enclosed in square brackets)."""
    match = re.match(r'\[(.*?)\]', file_name)
    if match:
        return match.group(1)
    return None

def group_files_by_client(files):
    """Group files by their client name (the tag in square brackets)."""
    grouped_files = defaultdict(list)
    for file_name in files:
        client_name = extract_client_name(file_name)
        if client_name:
            grouped_files[client_name].append(file_name)
    return grouped_files

def unzip_file(zip_file_path, extract_to_folder):
    """Unzip the ZIP file to a temporary folder."""
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to_folder)
        logging.info(f"Unzipped file '{zip_file_path}' to '{extract_to_folder}'.")
        return [os.path.join(extract_to_folder, f) for f in os.listdir(extract_to_folder)]
    except zipfile.BadZipFile:
        logging.error(f"Failed to unzip file: {zip_file_path}")
        return []

def encode_file_to_base64(file_path):
    """Encode the file to base64 for sending in the attachment."""
    with open(file_path, 'rb') as file:
        encoded_string = base64.b64encode(file.read()).decode('utf-8')
    return encoded_string

def get_main_contact_for_organization(organization_name):
    """Retrieve the main contact (user) for a given organization and ensure they have an email address."""
    try:
        # URL-encode the organization name to handle spaces and special characters
        encoded_org_name = urllib.parse.quote(organization_name)

        # Make a single API call to search for users in the organization by name
        user_response = requests.get(f"{api_url}/users/search?query=organization.name:{encoded_org_name}", headers=headers)
        user_response.raise_for_status()

        users = user_response.json()
        
        # Step 2: Find the user who is the main contact and has a valid email address
        for user in users:
            if user.get('main_contact', False):
                email = user.get('email')
                if email:
                    logging.info(f"Main contact for organization '{organization_name}' is {user['firstname']} {user['lastname']} (ID: {user['id']}, Email: {email}).")
                    return user['id'], email  # Return the customer_id and email of the main contact
                else:
                    logging.error(f"Main contact for organization '{organization_name}' has no valid email address.")
                    return None, None

        logging.error(f"No main contact found for organization '{organization_name}'.")
        return None, None

    except requests.HTTPError as http_err:
        logging.error(f"HTTP error occurred while fetching organization users: {http_err}")
    except Exception as err:
        logging.error(f"Other error occurred: {err}")
    return None, None

def create_zammad_ticket_with_main_contact(client_name, customer_id, customer_email, file_list):
    """Create a ticket in Zammad for the given customer and attach the files in the first article."""
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Generate title, subject, and body dynamically
    ticket_title = title_template.format(client_name=client_name, date=current_date)
    article_subject = subject_template.format(client_name=client_name, date=current_date)
    article_body = body_template.format(client_name=client_name, files_list=', '.join([os.path.basename(f) for f in file_list]))

    # Prepare the attachments
    attachments = []
    for file_path in file_list:
        file_name = os.path.basename(file_path)
        encoded_file = encode_file_to_base64(file_path)
        attachments.append({
            'filename': file_name,
            'data': encoded_file,
            'mime-type': 'application/pdf' if file_name.endswith('.pdf') else 'application/octet-stream'
        })

    # Prepare ticket data with customer_id and customer_email in the "to" field
    ticket_data = {
        'title': ticket_title,
        'group': group,
        'article': {
            'subject': article_subject,
            'body': article_body,
            'type': 'email',  # Email type
            'content_type': 'text/plain',
            'to': customer_email,  # Add the email of the main contact as the recipient
            'internal': False,  # This must be False to send an external email
            'attachments': attachments
        },
        'customer_id': customer_id,  # This links the ticket to a specific customer
        'customertype': customertype
    }

    try:
        response = requests.post(f"{api_url}/tickets", headers=headers, json=ticket_data)
        response.raise_for_status()
        ticket_id = response.json().get('id')
        logging.info(f"Ticket {ticket_id} created successfully for customer {client_name} with attachments.")
        return ticket_id
    except requests.HTTPError as http_err:
        logging.error(f"Failed to create ticket: {http_err}")
        logging.error(f"Response content: {response.content.decode('utf-8')}")
        return None

def create_internal_note(ticket_id):
    """Add an internal note to the created ticket."""
    note_data = {
        'ticket_id': ticket_id,
        'subject': "Internal Note",
        'body': "Ticket registered programmatically via API. Visit https://github.com/0xluiz for further details.",
        'type': 'note',
        'internal': True  # This marks it as an internal note
    }

    try:
        response = requests.post(f"{api_url}/ticket_articles", headers=headers, json=note_data)
        response.raise_for_status()
        logging.info(f"Internal note added to ticket {ticket_id} successfully.")
    except requests.HTTPError as http_err:
        logging.error(f"Failed to add internal note to ticket {ticket_id}: {http_err}")
        logging.error(f"Response content: {response.content.decode('utf-8')}")

def move_files(source_files, source_folder, destination_folder):
    """Move processed files to a destination folder."""
    for file_name in source_files:
        source_file_path = os.path.join(source_folder, file_name)
        dest_file_path = os.path.join(destination_folder, file_name)
        try:
            shutil.move(source_file_path, dest_file_path)
            logging.info(f"Moved file '{file_name}' to {destination_folder}.")
        except FileNotFoundError:
            logging.error(f"File not found: {source_file_path}")
        except PermissionError:
            logging.error(f"Permission denied to move file: {source_file_path}")
        except Exception as e:
            logging.error(f"Error moving file {file_name}: {e}")

if __name__ == '__main__':
    # Step 1: Get all files from the source folder
    files = get_files_in_folder(source_folder)

    if not files:
        logging.info("No ZIP files found in the folder.")
        exit()

    # Step 2: Group files by client name
    grouped_files = group_files_by_client(files)

    if not grouped_files:
        logging.info("No valid client-tagged files found.")
        exit()

    # Step 3: Create tickets with attachments for the main contact of the organization
    for client_name, file_list in grouped_files.items():
        all_files_to_attach = []
        for zip_file_name in file_list:
            zip_file_path = os.path.join(source_folder, zip_file_name)
            # Step 4: Unzip the file
            unzipped_files = unzip_file(zip_file_path, temp_unzip_folder)
            if unzipped_files:
                all_files_to_attach.extend(unzipped_files)

        # Step 5: Get the main contact's customer_id and email for the organization
        customer_id, email = get_main_contact_for_organization(client_name)

        if customer_id and email:  # Ensure both customer_id and email are valid
            # Step 6: Create the ticket for the customer with the attachments in the first article
            ticket_id = create_zammad_ticket_with_main_contact(client_name, customer_id, email, all_files_to_attach)

            if ticket_id:
                # Step 7: Add an internal note to the ticket
                create_internal_note(ticket_id)

                # Step 8: Move processed files to the processed folder
                move_files(file_list, source_folder, processed_folder)  # Move ZIP files to processed
                move_files(os.listdir(temp_unzip_folder), temp_unzip_folder, processed_folder)  # Move unzipped files
        else:
            logging.error(f"Ticket for '{client_name}' not created because main contact has no email or could not be found.")

        # Clean up the temporary unzip folder after each customer is processed
        shutil.rmtree(temp_unzip_folder)
        os.makedirs(temp_unzip_folder)  # Recreate the folder for the next iteration
