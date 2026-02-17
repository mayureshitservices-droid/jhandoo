#!/usr/bin/env python3
import os
import shutil
import zipfile
import mysql.connector
from datetime import datetime
from dotenv import load_dotenv

def create_backup():
    load_dotenv()
    
    # Configuration
    project_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = os.path.join(project_dir, "backups")
    backup_folder = os.path.join(backup_root, f"jhandoo_backup_{timestamp}")
    
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)
        
    print(f"🚀 Starting backup: {timestamp}")
    
    # 1. Backup Code (Zip)
    zip_path = os.path.join(backup_folder, "source_code.zip")
    exclude_dirs = {'.venv', '__pycache__', '.git', 'backups'}
    exclude_files = {'.env'} # Don't zip .env directly for security, but we'll handle it below
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
            
            for file in files:
                if file not in exclude_files and not file.startswith('.'):
                    rel_path = os.path.relpath(os.path.join(root, file), project_dir)
                    zipf.write(os.path.join(root, file), rel_path)
    
    # Copy .env.example instead of .env to keep it safe but documented
    if os.path.exists(os.path.join(project_dir, ".env.example")):
        shutil.copy2(os.path.join(project_dir, ".env.example"), os.path.join(backup_folder, ".env.example"))
    
    print("✅ Source code zipped.")
    
    # 2. Backup Database
    try:
        config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DATABASE', 'ai_demo')
        }
        
        db_backup_path = os.path.join(backup_folder, f"database_export.sql")
        
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        print(f"📦 Exporting database: {config['database']}...")
        
        with open(db_backup_path, 'w', encoding='utf-8') as f:
            f.write(f"-- Jhandoo Database Backup\n")
            f.write(f"-- Created: {datetime.now()}\n\n")
            f.write(f"SET FOREIGN_KEY_CHECKS = 0;\n\n")
            
            cursor.execute("SHOW TABLES")
            tables = [t[0] for t in cursor.fetchall()]
            
            for table in tables:
                # Get create table statement
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                create_stmt = cursor.fetchone()[1]
                f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                f.write(f"{create_stmt};\n\n")
                
                # Get data
                cursor.execute(f"SELECT * FROM `{table}`")
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        # Simple value formatting
                        vals = []
                        for v in row:
                            if v is None: vals.append("NULL")
                            elif isinstance(v, (int, float)): vals.append(str(v))
                            else: vals.append(f"'{str(v).replace("'", "''")}'")
                        
                        f.write(f"INSERT INTO `{table}` VALUES ({', '.join(vals)});\n")
                    f.write("\n")
            
            f.write(f"SET FOREIGN_KEY_CHECKS = 1;\n")
            
        print(f"✅ Database exported to {os.path.basename(db_backup_path)}")
        conn.close()
        
    except Exception as e:
        print(f"❌ Database backup failed: {e}")
    
    print(f"\n✨ Backup completed successfully!")
    print(f"📍 Location: {backup_folder}")
    print(f"Keep this folder safe!")

if __name__ == "__main__":
    create_backup()
