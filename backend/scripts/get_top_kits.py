import sqlite3
import pandas as pd
import json

def get_top_products():
    conn = sqlite3.connect('rag_seo.db')
    
    transmissions = ['4L60E', 'A604', 'JF011E', '6R80', '09G']
    results = {}
    
    for tx in transmissions:
        query = f"""
        SELECT title, sku, total_sold, price, handle
        FROM products 
        WHERE (transmission_code = '{tx}' OR title LIKE '%{tx}%')
        AND (title LIKE '%Master%' OR title LIKE '%Juego de Empaques%' OR title LIKE '%Banner%')
        ORDER BY total_sold DESC
        LIMIT 3
        """
        df = pd.read_sql_query(query, conn)
        results[tx] = df.to_dict('records')
    
    conn.close()
    return results

if __name__ == "__main__":
    data = get_top_products()
    print(json.dumps(data, indent=2))
