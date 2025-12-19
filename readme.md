# Wardrobe Project

Wardrobe is a Django-based project that serves as an image bed and database application. It uses Nginx for serving static files and handling SSL, and PostgreSQL for data storage.

See repo [here](https://github.com/tsukishima1321/wardrobe-vue) for the frontend part.

## Prerequisites

- Python 3.x
- PostgreSQLs
- Nginx
- OpenSSL (for backups)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd wardrobe
    ```

2.  **Install Python dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

### Environment Variables

The project relies on several environment variables. You need to set these in your environment (e.g., in `.bashrc`, `.profile`, or a `.env` file loaded by your system).

| Variable | Description |
| :--- | :--- |
| `django_secret_key` | The secret key for the Django application. |
| `wardrobe_db_password` | Password for the PostgreSQL database user (postgres). |
| `wardrobe_localhost` | The domain or host and port for the application (e.g., `http://127.0.0.1:8000`). |
| `wardrobe_db_name` | Name of the database to backup (used in backup scripts). |
| `wardrobe_backupdir` | Directory containing the public key for backup encryption and backup files. |

Example setup in `.bashrc`:
```bash
export django_secret_key='your-secret-key'
export wardrobe_db_password='your-db-password'
export wardrobe_localhost='https://127.0.0.1:8000'
export wardrobe_db_name='wardrobe'
export wardrobe_backupdir='/path/to/backup/keys'
```

### Database Setup

1.  Ensure PostgreSQL is running.
2.  Create a database named `wardrobe` (or match `wardrobe_db_name`).
3.  The project uses two databases:
    - `default`: SQLite3 (`db.sqlite3`), for internal Django data.
    - `business`: PostgreSQL (`wardrobe`), for CRUD of business data.

### Nginx Configuration

An example Nginx configuration is provided in `nginx-ref.conf`.

1.  **SSL Certificates:**
    Ensure you have SSL certificates generated and placed at:
    - `/path/to/ssl/your.domain.pem`
    - `/path/to/ssl/your.domain.key`
    Or update the paths in the Nginx config to match your setup.

2.  **Static Files:**
    Nginx is configured to serve static files directly.
    The alias of `/imagebed/`, `/backup/` and `/imagebed/thumbnails/` should point to the correct directories in your project (defined in `IMAGE_STORAGE_PATH`  and `THUMBNAIL_STORAGE_PATH` in `settings.py` and environment variables). 

3.  **Proxy Pass:**
    Requests are proxied to the Django application running on `127.0.0.1:8000`.

### Backup Configuration

The project includes scripts for encrypted database backups: `db_dump.sh` and `auto_db_dump.sh`.

1.  **Public Key:**
    You must generate a public key for encryption and place it at `$wardrobe_backupdir/public_key.pem`.

    ```bash
    # Generate private key
    openssl genrsa -out private_key.pem 2048
    # Extract public key
    openssl rsa -in private_key.pem -pubout -out public_key.pem
    ```

2. **How to decrypt and restore backups:**

   The backup script creates a `.tar.gz` file containing the encrypted database dump (`all.sql.enc`) and the encrypted symmetric key (`key.bin.enc`).

   To restore a backup:

   1.  **Extract the backup archive:**
       ```bash
       tar -xzf <timestamp>.tar.gz
       ```

   2.  **Decrypt the symmetric key:**
       Use your private key (`private_key.pem`) to decrypt the symmetric key.
       ```bash
       openssl pkeyutl -decrypt -inkey private_key.pem -in key.bin.enc -out key.bin
       ```

   3.  **Decrypt the database dump:**
       Use the decrypted symmetric key to decrypt the SQL dump.
       ```bash
       openssl enc -d -aes-256-cbc -pbkdf2 -salt -pass file:key.bin -in all.sql.enc -out all.sql
       ```

   4.  **Restore the database:**
       Load the SQL dump into PostgreSQL.
       ```bash
       psql -d $wardrobe_db_name -f all.sql
       ```
       *Note: Ensure you have created the database before restoring.*

   5.  **Clean up:**
       Remove the sensitive unencrypted files.
       ```bash
       rm key.bin all.sql
       ```


## Running the Project

1.  **Apply Migrations:**
    ```bash
    python manage.py migrate
    python manage.py migrate --database=business
    ```

2.  **Start the Development Server:**
    It is recommended to use a production server like daphne behind Nginx for deployment.
    ```bash
    daphne wardrobe.asgi:application
    ```

3.  **Start Nginx:**
    Ensure your Nginx configuration is active and Nginx is running.

4. **Auto Backup Setup:**
   You can set up a cron job to run `auto_db_dump.sh` at desired intervals for automated backups.
   You must grant SELECT privileges on all tables and sequences to the user running the backup script.

## API Endpoints Under Recommended Nginx Configuration

Authentication:
- `/auth/` - Authentication endpoints
- `/api/token/` - JWT token endpoints
- `/api/refresh/` - JWT token refresh endpoint

Static Files:
- `/imagebed/` - Static files for image bed
- `/imagebed/thumbnails/` - Thumbnails for image bed
- `/backup/` - Directory for accessing backups without lauchching Django

CRUD Operations:
- `/api/` - Main API endpoint for CRUD operations

You can customize and extend these endpoints by modifying nginx.conf to fit your deployment needs.
