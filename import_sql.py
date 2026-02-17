#!/usr/bin/env python3
import mysql.connector
import os
import re
from dotenv import load_dotenv

def import_sql_file(filename):
    load_dotenv()
    
    config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'database': os.getenv('MYSQL_DATABASE', 'ai_demo')
    }
    
    print(f"Connecting to {config['database']}...")
    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        print(f"Reading {filename}...")
        with open(filename, 'r', encoding='utf-8') as f:
            sql_file = f.read()
            
        # Split by semicolon, but handle cases where semicolon might be in strings
        # This is a basic split, but for standard SQL dumps it usually works
        # If it fails, we'd need a more complex regex or parser
        commands = re.split(r';(?=(?:[^\']|\'[^\']*\')*$)', sql_file)
        
        print(f"Executing {len(commands)} SQL commands...")
        count = 0
        for command in commands:
            cmd = command.strip()
            if not cmd or cmd.startswith('--') or cmd.startswith('/*'):
                continue
                
            try:
                cursor.execute(cmd)
                count += 1
                if count % 100 == 0:
                    print(f"Executed {count} commands...")
            except Exception as e:
                print(f"Error executing command: {cmd[:50]}...")
                print(f"Error: {e}")
                
        conn.commit()
        print(f"Successfully executed {count} commands!")
        conn.close()
        return True
        
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

if __name__ == "__main__":
    import_sql_file('data.sql')
