Here is a basic `README.md` template for your GitHub project:

---

# Zammad Ticket Automation Script

This repository contains a Python script that automates the creation of Zammad tickets based on files found in a specific directory. The script extracts client information from filenames, unzips the files, creates a ticket in Zammad, and attaches the unzipped files. An internal note is also added to each ticket, logging that it was created programmatically.

## Features

- **File Processing**: Monitors a folder for `.zip` files and unzips them.
- **Client Detection**: Extracts client names from the filenames in the format `[ClientName]filename.zip`.
- **Ticket Creation**: Automatically creates tickets in Zammad with appropriate details.
- **Email Attachment**: Adds attachments from the unzipped files to the tickets.
- **Internal Notes**: Adds internal notes to the created tickets, logging that they were created via API.
- **File Management**: Moves processed files to a different folder to prevent duplication.

## Requirements

- Python 3.x
- Zammad instance with API access
- Required Python libraries:
  - `requests`
  - `shutil`
  - `zipfile`
  - `base64`
  - `json`
  - `logging`

Install the required libraries with:

```bash
pip install requests
```

## Configuration

Before running the script, ensure the `config.json` file is properly set up with the following fields:

```json
{
  "api_config": {
    "zammad_api_url": "https://your_zammad_url_here/api/v1",
    "api_token": "your_api_token_here",
    "headers": {
      "Content-Type": "application/json"
    }
  },
  "folder_paths": {
    "source_folder": "/path/to/your/source/folder",
    "processed_folder": "/path/to/your/processed/folder",
    "temp_unzip_folder": "/path/to/your/temp/unzip/folder"
  },
  "ticket_settings": {
    "group": "Your Group Here",
    "customer_id": "Your Customer ID Here",
    "customertype": "Your Customertype Here",
    "title_template": "[{client_name}] {date} Relatorios",
    "subject_template": "[{client_name}] {date} Relatorios",
    "body_template": "Seguem relatórios em anexo para {client_name}:\n\n{files_list}.\n\n"
  }
}
```

### Parameters

- `zammad_api_url`: The URL of your Zammad API.
- `api_token`: Your API token for authentication with Zammad.
- `source_folder`: The folder containing the `.zip` files to process.
- `processed_folder`: The folder where processed files will be moved.
- `temp_unzip_folder`: The temporary folder used for unzipping files.
- `group`: The group in Zammad to assign the tickets to.
- `customer_id`: The default customer ID (used if no client information is found).
- `customertype`: The type of customer for the ticket.

## How to Run

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/zammad-ticket-automation.git
   cd zammad-ticket-automation
   ```

2. Edit the `config.json` file with your settings.

3. Run the script:

   ```bash
   python3 openticket.py
   ```

4. The script will process all `.zip` files in the `source_folder`, create tickets in Zammad, and attach the unzipped files.

## Example

The script expects files to have a format like:

```
[ClientName]report.zip
```

The script will unzip `report.zip`, create a Zammad ticket titled `[ClientName] {date} Relatorios`, and attach the unzipped files.
